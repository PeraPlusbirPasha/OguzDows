import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import {
  Activity,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Bell,
  Bluetooth,
  BookOpen,
  Bookmark,
  Braces,
  Calculator,
  CalendarDays,
  Camera,
  CaseSensitive,
  Check,
  CheckCheck,
  ChevronLeft,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Clock3,
  CloudSun,
  Code2,
  Columns2,
  ContactRound,
  Copy,
  Delete,
  Download,
  ExternalLink,
  File,
  FileCheck2,
  FolderClosed,
  FolderHeart,
  Globe2,
  Grip,
  Heart,
  Home,
  Image,
  Languages,
  LayoutGrid,
  Leaf,
  ListTodo,
  LockKeyhole,
  Mail,
  Map,
  Menu,
  MessageCircle,
  Minus,
  Mic,
  Moon,
  MoreHorizontal,
  Music2,
  Newspaper,
  NotebookPen,
  Palette,
  Pause,
  Phone,
  Plane,
  Play,
  Plus,
  Radio,
  RotateCcw,
  Ruler,
  Search,
  SendHorizontal,
  Settings2,
  Shapes,
  ShieldCheck,
  ShoppingBag,
  SignalHigh,
  SlidersHorizontal,
  Smartphone,
  Sparkles,
  Square,
  Sun,
  TextCursorInput,
  Trash2,
  Upload,
  VolumeX,
  Volume2,
  Wifi,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";
const icons: Record<string, LucideIcon> = {
  Activity,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Bell,
  Bluetooth,
  BookOpen,
  Bookmark,
  Braces,
  Calculator,
  CalendarDays,
  Camera,
  CaseSensitive,
  Check,
  CheckCheck,
  ChevronLeft,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Clock3,
  CloudSun,
  Code2,
  Columns2,
  ContactRound,
  Copy,
  Delete,
  Download,
  ExternalLink,
  File,
  FileCheck2,
  FolderClosed,
  FolderHeart,
  Globe2,
  Grip,
  Heart,
  Home,
  Image,
  Languages,
  LayoutGrid,
  Leaf,
  ListTodo,
  LockKeyhole,
  Mail,
  Map,
  Menu,
  MessageCircle,
  Minus,
  Mic,
  Moon,
  MoreHorizontal,
  Music2,
  Newspaper,
  NotebookPen,
  Palette,
  Pause,
  Phone,
  Plane,
  Play,
  Plus,
  Radio,
  RotateCcw,
  Ruler,
  Search,
  SendHorizontal,
  Settings2,
  Shapes,
  ShieldCheck,
  ShoppingBag,
  SignalHigh,
  SlidersHorizontal,
  Smartphone,
  Sparkles,
  Square,
  Sun,
  TextCursorInput,
  Trash2,
  Upload,
  VolumeX,
  Volume2,
  Wifi,
  X,
  Zap,
};
export function Icon({
  name,
  size = 20,
  className = "",
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  const Component = icons[name] || CircleHelp;
  return (
    <Component
      size={size}
      strokeWidth={1.8}
      aria-hidden="true"
      className={className}
    />
  );
}
export function Nazar({
  size = 32,
  power = false,
}: {
  size?: number;
  power?: boolean;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="32" cy="32" r="30" fill="#153f79" />
      <circle cx="32" cy="32" r="22" fill="#f3efdd" />
      <circle cx="32" cy="32" r="15" fill="#4db5cc" />
      <circle cx="32" cy="32" r="8" fill="#102c43" />
      {power && (
        <path
          d="M32 3v13"
          stroke="white"
          strokeWidth="4"
          strokeLinecap="round"
        />
      )}
      <circle cx="29" cy="29" r="2" fill="white" opacity=".8" />
    </svg>
  );
}
export function AppBadge({
  icon,
  color = "mint",
  small = false,
  artwork,
}: {
  icon: string;
  color?: string;
  small?: boolean;
  artwork?: string;
}) {
  const [failed, setFailed] = useState(false);
  return (
    <span
      className={`app-badge ${color} ${small ? "small" : ""} ${artwork && !failed ? "brand-artwork" : ""}`}
      aria-hidden="true"
    >
      {artwork && !failed ? (
        <img
          src={artwork}
          alt=""
          draggable={false}
          data-app-artwork="true"
          onError={() => setFailed(true)}
        />
      ) : (
        <Icon name={icon} size={small ? 21 : 28} />
      )}
    </span>
  );
}
export function Toggle({
  on,
  label,
  onChange,
}: {
  on: boolean;
  label: string;
  onChange: () => void;
}) {
  return (
    <button
      className={`toggle ${on ? "on" : ""}`}
      role="switch"
      aria-label={label}
      aria-checked={on}
      onClick={onChange}
    >
      <span />
    </button>
  );
}
export function ScreenTitle({
  title,
  eyebrow = "OĞUZDOWS",
  onBack,
  action,
}: {
  title: string;
  eyebrow?: string;
  onBack: () => void;
  action?: ReactNode;
}) {
  return (
    <header className="screen-title">
      <button
        className="icon-button"
        aria-label="Ana ekrana dön"
        onClick={onBack}
      >
        <Icon name="ArrowLeft" />
      </button>
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
      </div>
      {action}
    </header>
  );
}
export function Notice({
  children,
  icon = "CircleHelp",
}: {
  children: ReactNode;
  icon?: string;
}) {
  return (
    <div className="notice">
      <Icon name={icon} size={18} />
      <p>{children}</p>
    </div>
  );
}
export function Dialog({
  title,
  children,
  onClose,
  placement = "bottom",
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  placement?: "bottom" | "top";
}) {
  const titleId = useId();
  const dragStart = useRef<number | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    const focusable = () =>
      Array.from(
        ref.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled),a[href],input,textarea,select,[tabindex="0"]',
        ) || [],
      );
    focusable()[0]?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        closeRef.current();
      }
      if (e.key === "Tab") {
        const list = focusable();
        const first = list[0],
          last = list.at(-1);
        if (!first) return;
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    const node = ref.current;
    node?.addEventListener("keydown", key);
    return () => {
      node?.removeEventListener("keydown", key);
      if (before?.isConnected) before.focus();
    };
  }, []);
  return (
    <div className={`sheet-shade sheet-${placement}`} onClick={onClose}>
      <div
        ref={ref}
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sheet-grip" />
        <header>
          <h2 id={titleId}>{title}</h2>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Pencereyi kapat"
          >
            <Icon name="X" />
          </button>
        </header>
        <div className="sheet-body">{children}</div>
        {placement === "top" && (
          <button
            className="panel-dismiss"
            aria-label="Paneli kapat"
            onClick={onClose}
            onPointerDown={(event) => {
              dragStart.current = event.clientY;
              event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerUp={(event) => {
              if (
                dragStart.current !== null &&
                dragStart.current - event.clientY > 35
              )
                onClose();
              dragStart.current = null;
            }}
          >
            <span />
            <small>Yukarı kaydırarak kapat</small>
          </button>
        )}
      </div>
    </div>
  );
}
