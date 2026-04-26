"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/chat", label: "Chat" },
  { href: "/about", label: "About" },
  { href: "/blog", label: "Blog" },
  { href: "/legal", label: "Legal" },
];

export function TopNav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 px-4 pt-4 sm:px-8 [will-change:transform] [transform:translateZ(0)]">
      <nav className="mx-auto flex w-full max-w-6xl items-center justify-between rounded-2xl border border-accent/25 bg-[#0a1232]/60 px-4 py-3 shadow-[0_10px_36px_rgba(4,7,20,0.42)] backdrop-blur-lg sm:px-6">
        <Link
          href="/"
          className="text-xs font-semibold uppercase tracking-[0.24em] text-accent transition hover:text-[#ffe59f]"
        >
          GITAGPT
        </Link>
        <div className="flex flex-wrap items-center justify-end gap-x-4 gap-y-1 text-sm sm:gap-x-6">
          {navItems.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`transition ${
                  active
                    ? "text-accent"
                    : "text-muted-foreground hover:text-accent"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </header>
  );
}
