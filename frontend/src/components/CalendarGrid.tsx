import { useMemo } from 'react';
import type { CalendarSlot } from '../types';

interface CalendarGridProps {
  year: number;
  month: number; // 1-12
  slots: CalendarSlot[];
  onPrevMonth: () => void;
  onNextMonth: () => void;
  onSlotClick: (slot: CalendarSlot) => void;
  onEmptyDayClick: (date: string) => void;
}

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const STATUS_COLORS: Record<string, string> = {
  suggested: 'bg-blue-500/20 border-blue-500/40 text-blue-300',
  approved: 'bg-green-500/20 border-green-500/40 text-green-300',
  generating: 'bg-yellow-500/20 border-yellow-500/40 text-yellow-300',
  generated: 'bg-purple-500/20 border-purple-500/40 text-purple-300',
  skipped: 'bg-gray-500/20 border-gray-500/40 text-gray-400',
};

function formatTime(time24: string): string {
  const [hStr, mStr] = time24.split(':');
  const h = parseInt(hStr, 10);
  const suffix = h >= 12 ? 'PM' : 'AM';
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${h12}:${mStr} ${suffix}`;
}

const TYPE_EMOJI: Record<string, string> = {
  festival: '\uD83C\uDF89',
  trending: '\uD83D\uDD25',
  brand: '\u2B50',
  regular: '\uD83D\uDCDD',
};

export function CalendarGrid({
  year,
  month,
  slots,
  onPrevMonth,
  onNextMonth,
  onSlotClick,
  onEmptyDayClick,
}: CalendarGridProps) {
  const { days, startOffset } = useMemo(() => {
    const firstDay = new Date(year, month - 1, 1);
    const lastDay = new Date(year, month, 0);
    const daysInMonth = lastDay.getDate();
    // Monday = 0, Sunday = 6
    const offset = (firstDay.getDay() + 6) % 7;
    const daysArr: number[] = [];
    for (let i = 1; i <= daysInMonth; i++) daysArr.push(i);
    return { days: daysArr, startOffset: offset };
  }, [year, month]);

  const slotsByDate = useMemo(() => {
    const map: Record<string, CalendarSlot> = {};
    for (const s of slots) {
      map[s.slot_date] = s;
    }
    return map;
  }, [slots]);

  const today = new Date();
  const todayStr =
    today.getFullYear() === year && today.getMonth() + 1 === month
      ? String(today.getDate())
      : null;

  return (
    <div>
      {/* Month navigation */}
      <div className="mb-4 flex items-center justify-between">
        <button
          onClick={onPrevMonth}
          className="rounded-lg px-3 py-1.5 text-sm text-text-muted hover:bg-bg-elevated hover:text-text-primary transition-colors"
        >
          &larr; Prev
        </button>
        <h2 className="text-lg font-semibold text-text-primary">
          {MONTH_NAMES[month - 1]} {year}
        </h2>
        <button
          onClick={onNextMonth}
          className="rounded-lg px-3 py-1.5 text-sm text-text-muted hover:bg-bg-elevated hover:text-text-primary transition-colors"
        >
          Next &rarr;
        </button>
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-7 gap-1 mb-1">
        {DAYS.map((d) => (
          <div key={d} className="py-2 text-center text-xs font-medium text-text-muted">
            {d}
          </div>
        ))}
      </div>

      {/* Calendar cells */}
      <div className="grid grid-cols-7 gap-1">
        {/* Empty cells for offset */}
        {Array.from({ length: startOffset }).map((_, i) => (
          <div key={`empty-${i}`} className="min-h-24 rounded-lg bg-bg-page/50" />
        ))}

        {days.map((day) => {
          const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
          const slot = slotsByDate[dateStr];
          const isToday = todayStr === String(day);

          return (
            <button
              key={day}
              onClick={() => (slot ? onSlotClick(slot) : onEmptyDayClick(dateStr))}
              className={`group relative min-h-24 rounded-lg border p-2 text-left transition-colors hover:border-accent/50 ${
                isToday
                  ? 'border-accent/40 bg-accent/5'
                  : 'border-border bg-bg-card'
              }`}
            >
              {/* Day number */}
              <span
                className={`text-xs font-medium ${
                  isToday ? 'text-accent' : 'text-text-muted'
                }`}
              >
                {day}
              </span>

              {/* "+" hint on empty days */}
              {!slot && (
                <span className="absolute inset-0 flex items-center justify-center text-text-muted opacity-0 group-hover:opacity-40 transition-opacity text-2xl font-light pointer-events-none">
                  +
                </span>
              )}

              {/* Slot indicator */}
              {slot && (
                <div
                  className={`mt-1 rounded border px-1.5 py-1 ${STATUS_COLORS[slot.status] || STATUS_COLORS.suggested}`}
                >
                  <div className="flex items-center gap-1 text-[10px] font-medium leading-tight">
                    <span>{TYPE_EMOJI[slot.event_type || 'regular'] || ''}</span>
                    <span className="truncate">{slot.event_name || 'Post'}</span>
                  </div>
                  {slot.posting_time && (
                    <div className="mt-0.5 text-[9px] font-medium opacity-80">
                      {formatTime(slot.posting_time)}
                    </div>
                  )}
                  {slot.post_idea && (
                    <div className="mt-0.5 text-[9px] leading-tight opacity-70 line-clamp-2">
                      {slot.post_idea}
                    </div>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-3">
        {Object.entries(STATUS_COLORS).map(([status, cls]) => (
          <div key={status} className="flex items-center gap-1.5">
            <div className={`h-2.5 w-2.5 rounded-full border ${cls}`} />
            <span className="text-[10px] capitalize text-text-muted">{status}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
