import { useEffect, useState, useCallback, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useStore } from '../store/useStore';
import { useChat } from '../hooks/useChat';
import { uploadProductImage, updateBrand } from '../api/brands';
import { getPlan, saveSlots, addSlot, updateSlot, createSlotContent, updatePlanSession } from '../api/calendar';
import { createSession } from '../api/sessions';
import { CalendarGrid } from '../components/CalendarGrid';
import { CalendarPopover, type SlotConfig } from '../components/CalendarPopover';
import { AddSlotPopover, type AddSlotData } from '../components/AddSlotPopover';
import { CalendarSidebar } from '../components/CalendarSidebar';
import type { Brand, CalendarPlan, CalendarSlot, CalendarSlotUpdate } from '../types';

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

type SidebarMode = 'planner' | 'content';

export function Calendar() {
  const { selectedBrandId } = useStore();
  const { brands, refreshBrands, refreshSessions } = useOutletContext<{ brands: Brand[]; refreshBrands: () => void; refreshSessions: () => void }>();
  const selectedBrand = brands.find((b) => b.id === selectedBrandId);

  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [plan, setPlan] = useState<CalendarPlan | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<CalendarSlot | null>(null);
  const [addSlotDate, setAddSlotDate] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const maxDays = daysInMonth(year, month);
  const [postsCount, setPostsCount] = useState(selectedBrand?.max_posts_per_month ?? 12);

  const [sidebarMode, setSidebarMode] = useState<SidebarMode>('planner');
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [contentSlotId, setContentSlotId] = useState<string | null>(null);

  const plannerSessionRef = useRef<string | null>(null);
  const { messages, streaming, sendMessage, sendHidden, cancel } = useChat(activeSessionId || undefined);

  const pendingMessageRef = useRef<string | null>(null);

  // Gate flags: only true during active generation, NOT when restoring history
  const expectingPlanRef = useRef(false);
  const expectingContentRef = useRef(false);

  // Track processed campaign post dates to avoid duplicate slot creation
  const processedCampaignDatesRef = useRef<Set<string>>(new Set());

  // When regenerating a single slot, track its date so the plan watcher
  // uses addSlot (upsert) instead of saveSlots (bulk replace)
  const regeneratingSlotDateRef = useRef<string | null>(null);

  // Track the last processed plan message ID to avoid re-processing old plans
  // when expectingPlanRef is re-enabled for regeneration
  const lastProcessedPlanMsgIdRef = useRef<string | null>(null);

  // Fetch plan when brand/month changes — full reset
  useEffect(() => {
    if (!selectedBrandId) return;

    // Cancel any in-flight SSE stream from the previous month
    cancel();

    // Clean reset all session/chat state
    setActiveSessionId(null);
    plannerSessionRef.current = null;
    setContentSlotId(null);
    pendingMessageRef.current = null;
    setSelectedSlot(null);
    expectingPlanRef.current = false;
    expectingContentRef.current = false;
    processedCampaignDatesRef.current = new Set();
    lastProcessedPlanMsgIdRef.current = null;
    setSidebarMode('planner');
    const days = daysInMonth(year, month);
    const brandDefault = brands.find((b) => b.id === selectedBrandId)?.max_posts_per_month ?? 12;
    setPostsCount(Math.min(brandDefault, days));

    setLoading(true);
    getPlan(selectedBrandId, year, month)
      .then((loadedPlan) => {
        setPlan(loadedPlan);
        // Restore planner session if this month already has one
        if (loadedPlan.planner_session_id) {
          plannerSessionRef.current = loadedPlan.planner_session_id;
          setActiveSessionId(loadedPlan.planner_session_id);
          setSidebarMode('planner');
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [selectedBrandId, year, month]);

  // When activeSessionId changes AND we have a pending message, send it
  useEffect(() => {
    if (activeSessionId && pendingMessageRef.current && !streaming) {
      const msg = pendingMessageRef.current;
      pendingMessageRef.current = null;
      sendHidden(msg);
    }
  }, [activeSessionId, streaming, sendHidden]);

  // Watch for interactive responses containing calendar_plan (planner mode)
  // Only processes messages when expectingPlanRef is true (active generation)
  useEffect(() => {
    if (!plan || sidebarMode !== 'planner') return;
    if (!expectingPlanRef.current) return; // Skip when restoring history

    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.interactive?.media && 'calendar_plan' in (msg.interactive.media as Record<string, unknown>)) {
        // Skip if this is the same plan message we already processed
        // (prevents re-processing old plans when expectingPlanRef is re-enabled)
        if (msg.id === lastProcessedPlanMsgIdRef.current) break;

        const calendarPlan = (msg.interactive.media as Record<string, unknown>).calendar_plan;
        if (Array.isArray(calendarPlan) && calendarPlan.length > 0) {
          // Guard: verify slot dates belong to the current plan's month
          const firstDate = (calendarPlan[0] as Record<string, unknown>)?.date;
          if (typeof firstDate === 'string') {
            const d = new Date(firstDate + 'T00:00:00');
            if (d.getFullYear() !== year || d.getMonth() + 1 !== month) {
              break; // Stale data from a different month's session
            }
          }
          expectingPlanRef.current = false; // Done — don't re-process
          lastProcessedPlanMsgIdRef.current = msg.id; // Remember this message

          const regenDate = regeneratingSlotDateRef.current;
          regeneratingSlotDateRef.current = null;

          if (regenDate) {
            // Regenerating a single slot — find the matching slot in the
            // agent's response and upsert ONLY that one (preserves manual slots)
            const match = calendarPlan.find(
              (s: Record<string, unknown>) => s.date === regenDate
            ) as Record<string, string> | undefined;
            if (match) {
              addSlot(plan.id, {
                date: match.date,
                event_name: match.event_name,
                event_type: match.event_type,
                post_idea: match.post_idea,
                post_type: match.post_type,
                posting_time: match.posting_time,
                status: 'suggested',
              })
                .then((saved) => {
                  setPlan((prev) => {
                    if (!prev) return prev;
                    const exists = prev.slots.some((s) => s.slot_date === regenDate);
                    return {
                      ...prev,
                      slots: exists
                        ? prev.slots.map((s) => (s.slot_date === regenDate ? saved : s))
                        : [...prev.slots, saved],
                    };
                  });
                })
                .catch(console.error);
            }
          } else {
            // Full plan generation — replace all slots
            saveSlots(plan.id, calendarPlan)
              .then((savedSlots) => {
                setPlan((prev) =>
                  prev ? { ...prev, status: 'active', slots: savedSlots } : prev
                );
              })
              .catch(console.error);
          }
          break;
        }
      }
    }
  }, [messages, plan, sidebarMode]);

  // Watch for campaign posts — detect campaign_post_date in any interactive message
  // and create calendar slots. Scans forward through ALL messages, independent of
  // expectingContentRef (which is only for single-slot content).
  useEffect(() => {
    if (sidebarMode !== 'content' || !plan || !activeSessionId) return;

    for (const msg of messages) {
      const media = msg.interactive?.media;
      if (!media?.image_path || !media.campaign_post_date) continue;

      const postDate = media.campaign_post_date;
      if (processedCampaignDatesRef.current.has(postDate)) continue;
      processedCampaignDatesRef.current.add(postDate);

      const imagePath = media.image_path;
      const caption = media.campaign_post_caption || '';
      const hashtags = media.campaign_post_hashtags || '';

      addSlot(plan.id, {
        date: postDate,
        status: 'generated',
        session_id: activeSessionId,
        generated_image: imagePath,
        caption,
        hashtags,
        post_type: 'campaign',
      })
        .then((saved) => {
          setPlan((prev) => {
            if (!prev) return prev;
            const exists = prev.slots.some((s) => s.slot_date === postDate);
            return {
              ...prev,
              slots: exists
                ? prev.slots.map((s) => (s.slot_date === postDate ? saved : s))
                : [...prev.slots, saved],
            };
          });
        })
        .catch(console.error);
    }
  }, [messages, sidebarMode, plan, activeSessionId]);

  // Watch for regular (non-campaign) generated content — persist image to DB
  // Only processes when expectingContentRef is true (active generation)
  useEffect(() => {
    if (sidebarMode !== 'content' || !contentSlotId) return;
    if (!expectingContentRef.current) return;

    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      const media = msg.interactive?.media;
      if (!media?.image_path) continue;

      // Skip campaign posts — handled by the separate campaign watcher
      if (media.campaign_post_date) continue;

      expectingContentRef.current = false;
      const imagePath = media.image_path;

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

      // Immediate local update for responsiveness
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
  }, [messages, sidebarMode, contentSlotId]);

  async function handleAddSlot(data: AddSlotData) {
    if (!plan) return;
    const date = addSlotDate;
    if (!date) return;
    setAddSlotDate(null);
    try {
      const saved = await addSlot(plan.id, { date, ...data, status: 'suggested' });
      setPlan((prev) => {
        if (!prev) return prev;
        const exists = prev.slots.some((s) => s.slot_date === date);
        return {
          ...prev,
          slots: exists
            ? prev.slots.map((s) => (s.slot_date === date ? saved : s))
            : [...prev.slots, saved],
        };
      });
    } catch (err) {
      console.error('Failed to add slot:', err);
    }
  }

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

    // Mark that we're actively generating — enables the plan watcher
    expectingPlanRef.current = true;

    try {
      const session = await createSession({ brand_id: selectedBrandId, agent_type: 'content_calendar' });

      // Link plan to session BEFORE sending — backend uses this to inject calendar context
      if (plan?.id) {
        await updatePlanSession(plan.id, session.id);
      }

      plannerSessionRef.current = session.id;
      pendingMessageRef.current = `Plan ${postsCount} posts`;
      setSidebarMode('planner');
      setActiveSessionId(session.id);
      refreshSessions();
    } catch (err) {
      expectingPlanRef.current = false;
      console.error('Failed to create planning session:', err);
    }
  }

  // Generate content for a slot — stays on calendar, uses sidebar
  async function handleGenerateContent(slotId: string, config?: SlotConfig) {
    if (!selectedBrandId || streaming) return;

    const slot = plan?.slots.find((s) => s.id === slotId);
    if (!slot) return;

    // Mark that we're actively generating content — enables the content watcher
    expectingContentRef.current = true;

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

      setContentSlotId(slotId);
      setSidebarMode('content');
      setSelectedSlot(null);
      refreshSessions();

      const idea = slot.post_idea || slot.event_name || 'a branded post';
      const eventContext = slot.event_name ? ` for ${slot.event_name} on ${slot.slot_date}` : '';

      // Build config instructions
      let configInstructions = '';
      if (config?.image_size) configInstructions += ` Image size: ${config.image_size}.`;
      if (config?.font_style) configInstructions += ` Font style: ${config.font_style}.`;
      if (config?.aspect_ratio) configInstructions += ` Aspect ratio: ${config.aspect_ratio}.`;
      if (config?.duration) configInstructions += ` Duration: ${config.duration} seconds.`;

      // Build System Context block for agents that parse it (size/font/aspect_ratio)
      const systemContext = configInstructions.trim()
        ? ` [System Context:${configInstructions}]`
        : '';

      // Sales poster: tell it to skip interactive phases and use product images from brand context
      if (result.agent_type === 'sales_poster') {
        pendingMessageRef.current = `Create a sales poster${eventContext}: ${idea}. Use the product images from the brand context. Skip the welcome and product info phases — go directly to choosing a headline, then show the image prompt for approval.${systemContext}`;
      } else if (result.agent_type === 'product_video') {
        pendingMessageRef.current = `Create a product video${eventContext}: ${idea}. Use the product images from the brand context. Skip the suggestion phase — go straight to creating the video.${systemContext}`;
      } else if (result.agent_type === 'campaign') {
        pendingMessageRef.current = `Plan a campaign${eventContext}: ${idea}. Ask me about campaign duration, posting frequency, and content mix before generating any content.${systemContext}`;
      } else {
        pendingMessageRef.current = `Create this specific post${eventContext}: ${idea}. Skip the suggestion phase — go straight to writing the image prompt and showing it for approval.${configInstructions}`;
      }
      setActiveSessionId(result.session_id);
    } catch (err) {
      expectingContentRef.current = false;
      console.error('Failed to create content session:', err);
    }
  }

  // View an existing content session for a slot (when clicking a generated/generating slot)
  function handleViewSlotSession(slot: CalendarSlot) {
    if (!slot.session_id) return;

    // Viewing history — don't enable the content watcher
    expectingContentRef.current = false;
    setContentSlotId(slot.id);
    setSidebarMode('content');
    setSelectedSlot(null);
    setActiveSessionId(slot.session_id);
  }

  function handleBackToPlanner() {
    expectingContentRef.current = false;
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

  async function handleApproveAndGenerate(slotId: string, config?: SlotConfig) {
    if (!selectedBrandId || streaming) return;
    try {
      // Save config to metadata_json if provided
      const updateData: CalendarSlotUpdate = { status: 'approved' };
      if (config && Object.keys(config).length > 0) {
        updateData.metadata_json = config as Record<string, unknown>;
      }
      await handleSlotUpdate(slotId, updateData);
      setSelectedSlot(null);
      await handleGenerateContent(slotId, config);
    } catch (err) {
      console.error('Failed to approve and generate:', err);
    }
  }

  // Regenerate a single slot's idea via the planner
  function handleRegenerateSlot(slot: CalendarSlot) {
    setSelectedSlot(null);

    // If no planner session exists, can't regenerate a single slot — need full plan first
    if (!plannerSessionRef.current) {
      triggerPlanGeneration();
      return;
    }

    // Enable the plan watcher so the updated plan gets saved
    expectingPlanRef.current = true;
    regeneratingSlotDateRef.current = slot.slot_date;

    const dateStr = slot.slot_date;
    const msg = `Regenerate ${dateStr}`;

    if (activeSessionId === plannerSessionRef.current && sidebarMode === 'planner') {
      // Already on the planner session — send directly
      sendMessage(msg);
    } else {
      // Need to switch to planner session first — use pending message
      expectingContentRef.current = false;
      setSidebarMode('planner');
      setContentSlotId(null);
      pendingMessageRef.current = msg;
      setActiveSessionId(plannerSessionRef.current);
    }
  }

  async function handleUploadProductImage(file: File) {
    if (!selectedBrandId) return;
    try {
      const result = await uploadProductImage(file);
      await updateBrand(selectedBrandId, { product_images: [result.image_path] });
      refreshBrands();
    } catch (err) {
      console.error('Failed to upload product image:', err);
    }
  }

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
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <label className="text-xs text-text-muted whitespace-nowrap">Posts:</label>
              <div className="flex items-center rounded-md border border-border bg-bg-surface">
                <button
                  onClick={() => setPostsCount((c) => Math.max(1, c - 1))}
                  disabled={streaming || loading || postsCount <= 1}
                  className="px-1.5 py-1 text-text-muted hover:text-text-primary disabled:opacity-30 transition-colors text-xs"
                >
                  -
                </button>
                <input
                  type="number"
                  min={1}
                  max={maxDays}
                  value={postsCount}
                  onChange={(e) => {
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v)) setPostsCount(Math.max(1, Math.min(maxDays, v)));
                  }}
                  disabled={streaming || loading}
                  className="w-8 bg-transparent text-center text-sm text-text-primary outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                />
                <button
                  onClick={() => setPostsCount((c) => Math.min(maxDays, c + 1))}
                  disabled={streaming || loading || postsCount >= maxDays}
                  className="px-1.5 py-1 text-text-muted hover:text-text-primary disabled:opacity-30 transition-colors text-xs"
                >
                  +
                </button>
              </div>
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
            onEmptyDayClick={setAddSlotDate}
          />
        )}
      </div>

      {/* Slot Popover */}
      {selectedSlot && (
        <CalendarPopover
          slot={selectedSlot}
          onClose={() => setSelectedSlot(null)}
          onUpdate={handleSlotUpdate}
          onApproveAndGenerate={handleApproveAndGenerate}
          onViewSession={handleViewSlotSession}
          onRegenerate={handleRegenerateSlot}
          hasProductImages={(selectedBrand?.product_images?.length ?? 0) > 0}
          onUploadProductImage={handleUploadProductImage}
        />
      )}

      {/* Add Slot Popover */}
      {addSlotDate && (
        <AddSlotPopover
          date={addSlotDate}
          onSubmit={handleAddSlot}
          onClose={() => setAddSlotDate(null)}
        />
      )}
    </div>
  );
}
