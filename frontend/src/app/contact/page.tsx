import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contact | GitaGPT Mentor",
  description: "Contact details for GitaGPT Mentor.",
  alternates: { canonical: "https://gitagpt.tech/contact" },
};

export default function ContactPage() {
  return (
    <main className="relative h-[var(--app-height,100dvh)] overflow-y-auto overflow-x-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(255,215,0,0.12),transparent_32%),linear-gradient(145deg,#05081c,#0a1740_38%,#201545_68%,#060718_100%)]" />
      <section className="relative mx-auto max-w-4xl px-6 py-20">
        <div className="rounded-3xl border border-border/70 bg-card/55 p-8 backdrop-blur-xl sm:p-10">
          <h1 className="text-4xl font-semibold font-[var(--font-heading)]">Contact</h1>
          <p className="mt-5 text-base leading-8 text-muted-foreground">Reach out at pavansai.bheemisetty@gmail.com or +91 7731911449.</p>
        </div>
      </section>
    </main>
  );
}
