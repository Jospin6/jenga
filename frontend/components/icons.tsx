import type { CSSProperties } from "react";

export type IconName = "spark" | "plus" | "grid" | "arrow" | "chevron" | "folder" | "code" | "eye" | "monitor" | "phone" | "refresh" | "download" | "copy" | "stop" | "check" | "file" | "globe" | "close" | "menu" | "loader" | "arrow-left";
const paths: Record<IconName, React.ReactNode> = {
  spark: <>
    <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z" />
    <path d="m20 2 .6 1.4L22 4l-1.4.6L20 6l-.6-1.4L18 4l1.4-.6L20 2Z" />
  </>,
  plus: <path d="M12 5v14M5 12h14" />,
  grid: <>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
  </>,
  arrow: <path d="M12 19V5m-6 6 6-6 6 6" />,
  chevron: <path d="m9 5 7 7-7 7" />,
  folder: <path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />,
  code: <>
    <path d="m7 6-6 6 6 6m10-12 6 6-6 6m-3-15-4 18" />
  </>,
  eye: <>
    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
    <circle cx="12" cy="12" r="3" />
  </>,
  monitor: <>
    <rect x="2" y="3" width="20" height="14" rx="2" />
    <path d="M12 17v4m-4 0h8" />
  </>,
  phone: <>
    <rect x="6" y="2" width="12" height="20" rx="2.5" />
    <path d="M10 18h4" />
  </>,
  refresh: <>
    <path d="M20 7a9 9 0 1 0 1 9M20 2v6h-6" />
  </>,
  download: <>
    <path d="M12 3v12m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4" />
  </>,
  copy: <>
    <rect x="8" y="8" width="13" height="13" rx="2" />
    <path d="M16 8V4a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h4" />
  </>,
  stop: <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none" />,
  check: <path d="m5 12 4 4L19 6" />,
  file: <>
    <path d="M14 2H5a1 1 0 0 0-1 1v18a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V8l-6-6Z" />
    <path d="M14 2v6h6M8 13h8m-8 4h6" />
  </>,
  globe: <>
    <circle cx="12" cy="12" r="9" />
    <ellipse cx="12" cy="12" rx="4" ry="9" />
    <path d="M3 12h18" />
  </>,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  loader: <path d="M21 12a9 9 0 1 1-9-9" />,
  "arrow-left": <path d="M20 12H4m6-6-6 6 6 6" />,
};

export function Icon({ name, size = 18, className = "", style }: { name: IconName; size?: number; className?: string; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" className={className} style={style} aria-hidden="true">{paths[name]}</svg>;
}

export function BrandMark({ small = false }: { small?: boolean }) {
  return <span className={`brand-mark ${small ? "small" : ""}`} aria-hidden="true">
    <svg viewBox="0 0 32 32" fill="none">
      <path d="M16 5v22M5 16h22M8.2 8.2l15.6 15.6M8.2 23.8 23.8 8.2" stroke="currentColor" strokeWidth="4.5" strokeLinecap="round" />
    </svg>
  </span>;
}
