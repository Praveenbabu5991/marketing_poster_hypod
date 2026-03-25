import { useEffect, useState, useCallback, useRef } from 'react';
import { useStore } from '../store/useStore';
import { useChat } from '../hooks/useChat';
import { getPlan, saveSlots, updateSlot, createSlotContent } from '../api/calendar';
import { createSession } from '../api/sessions';
import { CalendarGrid } from '../components/CalendarGrid';
import { CalendarPopover } from '../components/CalendarPopover';
import { CalendarSidebar } from '../components/CalendarSidebar';
import type { CalendarPlan, CalendarSlot, CalendarSlotUpdate } from '../types';

function buildPlanMessage(year: number, month: number): string {
  const today = new Date();
  const isCurrentMonth = today.getFullYear() === year && today.getMonth() + 1 === month;
  const monthName = new Date(year, month - 1).toLocaleString('en-US', { month: 'long' });

  if (isCurrentMonth) {
    const day = today.getDate();
    const lastDay = new Date(year, month, 0).getDate();
    const remaining = lastDay - day;
    return `Plan content for the remaining ${remaining} days of ${monthName} ${year} (from ${monthName} ${day} to ${monthName} ${lastDay}). Only create slots for dates from ${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')} onwards. Do NOT create any slots for dates before today.`;
  }
  return `Plan ${monthName} ${year}`;
}

type SidebarMode = 'planner' | 'content';

export function Calendar() {
  const { selectedBrandId } = useStore();

  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [plan, setPlan] = useState<CalendarPlan | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<CalendarSlot | null>(null);
  const [loading, setLoading] = useState(false);

  const [sidebarMode, setSidebarMode] = useState<SidebarMode>('planner');
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [contentSlotId, setContentSlotId] = useState<string | null>(null);

  const plannerSessionRef = useRef<string | null>(null);
  const { messages, streaming, sendMessage, sendHidden } = useChat(activeSessionId || undefined);

  const pendingMessageRef = useRef<string | null>(null);
  const autoTriggeredRef = useRef<string | null>(null);
  const savedPlanMsgIdRef = useRef<string | null>(null);
  // Track which content image we've already persisted to DB
  const savedContentMsgIdRef = useRef<string | null>(null);

  // Fetch plan when brand/month changes
  useEffect(() => {
    if (!selectedBrandId) return;
    setLoading(true);
    autoTriggeredRef.current = null;
    savedPlanMsgIdRef.current = null;
    savedContentMsgIdRef.current = null;
    setSidebarMode('planner');
    getPlan(selectedBrandId, year, month)
      .then(setPlan)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [selectedBrandId, year, month]);

  // Auto-generate plan when a draft plan loads with no slots
  useEffect(() => {
    if (!plan || !selectedBrandId) return;
    if (plan.status !== 'draft' || plan.slots.length > 0) return;
    if (streaming || loading) return;

    const key = `${selectedBrandId}-${year}-${month}`;
    if (autoTriggeredRef.current === key) return;
    autoTriggeredRef.current = key;

    triggerPlanGeneration();
  }, [plan, selectedBrandId, streaming, loading]);

  // When activeSessionId changes AND we have a pending message, send it
  useEffect(() => {
    if (activeSessionId && pendingMessageRef.current && !streaming) {
      const msg = pendingMessageRef.current;
      pendingMessageRef.current = null;
      sendHidden(msg);
    }
  }, [activeSessionId, streaming, sendHidden]);

  // Watch for interactive responses containing calendar_plan (planner mode)
  useEffect(() => {
    if (!plan || sidebarMode !== 'planner') return;

    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.interactive?.media && 'calendar_plan' in (msg.interactive.media as Record<string, unknown>)) {
        if (savedPlanMsgIdRef.current === msg.id) break;

        const calendarPlan = (msg.interactive.media as Record<string, unknown>).calendar_plan;
        if (Array.isArray(calendarPlan) && calendarPlan.length > 0) {
          savedPlanMsgIdRef.current = msg.id;
          saveSlots(plan.id, calendarPlan)
            .then((savedSlots) => {
              setPlan((prev) =>
                prev ? { ...prev, status: 'active', slots: savedSlots } : prev
              );
            })
            .catch(console.error);
          break;
        }
      }
    }
  }, [messages, plan, sidebarMode]);

  // Watch for generated content (content mode) — persist image to DB
  useEffect(() => {
    if (sidebarMode !== 'content' || !contentSlotId) return;

    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.interactive?.media?.image_path) {
        // Already persisted this message
        if (savedContentMsgIdRef.current === msg.id) break;
        savedContentMsgIdRef.current = msg.id;

        const imagePath = msg.interactive.media.image_path;

        // Persist to DB via PATCH
        updateSlot(contentSlotId, { status: 'generated' })
          .then((updated) => {
            setPlan((prev) => {
              if (!prev) return prev;
              return {
                ...prev,
                slots: prev.slots.map((s) =>
                  s.id === contentSlotId
                    ? { ...s, ...updated, generated_image: imagePath }
                    : s
                ),
              };
            });
          })
          .catch(console.error);

        // Also update local state immediately for responsiveness
        setPlan((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            slots: prev.slots.map((s) =>
              s.id === contentSlotId
                ? { ...s, status: 'generated', generated_image: imagePath }
                : s
            ),
          };
        });
        break;
      }
    }
  }, [messages, sidebarMode, contentSlotId]);

  function handlePrevMonth() {
    if (month === 1) { setYear(year - 1); setMonth(12); }
    else setMonth(month - 1);
  }

  function handleNextMonth() {
    if (month === 12) { setYear(year + 1); setMonth(1); }
    else setMonth(month + 1);
  }

  async function triggerPlanGeneration() {
    if (!selectedBrandId || streaming) return;

    try {
      const session = await createSession({ brand_id: selectedBrandId, agent_type: 'content_calendar' });
      plannerSessionRef.current = session.id;
      pendingMessageRef.current = buildPlanMessage(year, month);
      setSidebarMode('planner');
      setActiveSessionId(session.id);
    } catch (err) {
      console.error('Failed to create planning session:', err);
    }
  }

  // Generate content for a slot — stays on calendar, uses sidebar
  async function handleGenerateContent(slotId: string) {
    if (!selectedBrandId || streaming) return;

    const slot = plan?.slots.find((s) => s.id === slotId);
    if (!slot) return;

    try {
      const result = await createSlotContent(slotId);

      setPlan((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          slots: prev.slots.map((s) =>
            s.id === slotId ? { ...s, status: 'generating', session_id: result.session_id } : s
          ),
        };
      });

      savedContentMsgIdRef.current = null;
      setContentSlotId(slotId);
      setSidebarMode('content');
      setSelectedSlot(null);

      const idea = slot.post_idea || slot.event_name || 'a branded post';
      const eventContext = slot.event_name ? ` for ${slot.event_name} on ${slot.slot_date}` : '';
      pendingMessageRef.current = `Create this specific post${eventContext}: ${idea}. Skip the suggestion phase — go straight to writing the image prompt and showing it for approval.`;
      setActiveSessionId(result.session_id);
    } catch (err) {
      console.error('Failed to create content session:', err);
    }
  }

  // View an existing content session for a slot (when clicking a generated/generating slot)
  function handleViewSlotSession(slot: CalendarSlot) {
    if (!slot.session_id) return;

    setContentSlotId(slot.id);
    setSidebarMode('content');
    setSelectedSlot(null);
    setActiveSessionId(slot.session_id);
  }

  function handleBackToPlanner() {
    setSidebarMode('planner');
    setContentSlotId(null);
    if (plannerSessionRef.current) {
      setActiveSessionId(plannerSessionRef.current);
    }
  }

  const handleSidebarMessage = useCallback(
    (text: string) => {
      if (!activeSessionId) {
        triggerPlanGeneration();
        return;
      }
      sendMessage(text);
    },
    [activeSessionId, sendMessage],
  );

  async function handleSlotUpdate(slotId: string, data: CalendarSlotUpdate) {
    try {
      const updated = await updateSlot(slotId, data);
      setPlan((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          slots: prev.slots.map((s) => (s.id === slotId ? updated : s)),
        };
      });
      setSelectedSlot((prev) => (prev?.id === slotId ? updated : prev));
    } catch (err) {
      console.error('Failed to update slot:', err);
    }
  }

  if (!selectedBrandId) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <p className="text-lg text-text-muted">Select a brand to start planning</p>
          <p className="mt-1 text-sm text-text-muted">Choose a brand from the sidebar</p>
        </div>
      </div>
    );
  }

  const activeContentSlot = contentSlotId ? plan?.slots.find((s) => s.id === contentSlotId) : null;

  return (
    <div className="flex h-full">
      {/* Sidebar: AI Chat */}
      <div className="w-72 shrink-0 border-r border-border bg-bg-card">
        <CalendarSidebar
          messages={messages}
          streaming={streaming}
          onSendMessage={handleSidebarMessage}
          planStatus={plan?.status || 'draft'}
          mode={sidebarMode}
          contentSlot={activeContentSlot || undefined}
          onBackToPlanner={handleBackToPlanner}
        />
      </div>

      {/* Main: Calendar Grid */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-text-primary">Content Calendar</h1>
            <p className="text-xs text-text-muted">
              {plan?.slots.length
                ? `${plan.slots.length} posts planned`
                : 'No posts planned yet'}
              {plan?.status === 'draft' && !streaming && ' — Generating plan automatically...'}
            </p>
          </div>
          <button
            onClick={triggerPlanGeneration}
            disabled={streaming || loading}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
          >
            {streaming ? (
              <span className="flex items-center gap-2">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Planning...
              </span>
            ) : plan?.status === 'active' ? (
              'Regenerate Plan'
            ) : (
              'Generate Plan'
            )}
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          </div>
        ) : (
          <CalendarGrid
            year={year}
            month={month}
            slots={plan?.slots || []}
            onPrevMonth={handlePrevMonth}
            onNextMonth={handleNextMonth}
            onSlotClick={setSelectedSlot}
            onEmptyDayClick={() => {}}
          />
        )}
      </div>

      {/* Slot Popover */}
      {selectedSlot && (
        <CalendarPopover
          slot={selectedSlot}
          onClose={() => setSelectedSlot(null)}
          onUpdate={handleSlotUpdate}
          onGenerateContent={handleGenerateContent}
          onViewSession={handleViewSlotSession}
        />
      )}
    </div>
  );
}
