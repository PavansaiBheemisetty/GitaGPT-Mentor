"use client";

import Link from "next/link";
import {
  ArrowRight,
  BrainCircuit,
  Briefcase,
  Clock3,
  GitBranch,
  Github,
  HeartHandshake,
  Linkedin,
  Mail,
  MessageCircle,
  Phone,
  Scale,
  Sparkles,
} from "lucide-react";
import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { TopNav } from "../marketing/TopNav";

const features = [
  {
    title: "Real-life contextual understanding",
    description:
      "Interprets your practical situations with nuance, not just keywords, to provide useful decision support.",
    icon: BrainCircuit,
  },
  {
    title: "Bhagavad Gita grounded guidance",
    description:
      "Responses are aligned with Dharmic principles and scripture-backed wisdom inspired by Krishna's teachings.",
    icon: Sparkles,
  },
  {
    title: "Career and emotional clarity",
    description:
      "Find direction during uncertainty, burnout, and overthinking through structured reflective guidance.",
    icon: Briefcase,
  },
  {
    title: "Ethical and moral dilemma support",
    description:
      "Navigate difficult value conflicts with balanced insights rooted in duty, integrity, and purpose.",
    icon: Scale,
  },
  {
    title: "Conversational memory",
    description:
      "Maintains continuity across discussions so guidance evolves with your context and growth.",
    icon: Clock3,
  },
  {
    title: "Real-time AI responses",
    description:
      "Fast, live responses designed for modern workflows while preserving depth and spiritual grounding.",
    icon: MessageCircle,
  },
];

const stats = [
  { label: "Conversations Guided", value: 1000, suffix: "+" },
  { label: "Chapters Referenced", value: 18, suffix: "" },
  { label: "Gita Passages Referenced", value: 100, suffix: "+" },
  { label: "AI Guidance", value: 24, suffix: "/7" },
];

const scenarios = [
  {
    title: "Career confusion and overthinking",
    text: "When ambition and doubt collide, GitaGPT helps you act with clarity instead of fear.",
  },
  {
    title: "Workplace betrayal and politics",
    text: "Navigate difficult teams with grounded composure, ethical strength, and strategic patience.",
  },
  {
    title: "Relationship and emotional conflicts",
    text: "Reflect before reacting with guidance that balances empathy, boundaries, and inner steadiness.",
  },
  {
    title: "Ethical and moral dilemmas",
    text: "Choose the next right step when values, pressure, and consequences all compete at once.",
  },
];

const testimonials = [
  "Felt like Krishna himself answered me.",
  "Helped me through career confusion.",
  "The first AI that understood my real-life situation.",
];

const upiId = "7731911449@slc";

function CountUpStat({ value, suffix, label }: { value: number; suffix: string; label: string }) {
  const [display, setDisplay] = useState(0);
  const ref = useRef<HTMLDivElement | null>(null);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setStarted(true);
          observer.disconnect();
        }
      },
      { threshold: 0.35 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!started) return;
    let frame = 0;
    const total = 36;
    const timer = window.setInterval(() => {
      frame += 1;
      const progress = Math.min(frame / total, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(value * eased));
      if (progress === 1) {
        window.clearInterval(timer);
      }
    }, 24);
    return () => window.clearInterval(timer);
  }, [started, value]);

  return (
    <div
      ref={ref}
      className="group rounded-2xl border border-border/70 bg-card/60 p-5 backdrop-blur transition duration-300 hover:-translate-y-1 hover:scale-[1.02] hover:border-accent/50 hover:shadow-halo"
    >
      <p className="text-3xl font-semibold text-accent font-[var(--font-heading)] sm:text-4xl">
        {display}
        {suffix}
      </p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{label}</p>
    </div>
  );
}

export function AboutPageContent() {
  const [copied, setCopied] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 768px)");
    const sync = () => setIsMobile(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  async function copyUpiId() {
    try {
      await navigator.clipboard.writeText(upiId);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <main className="relative min-h-screen bg-background text-foreground">
      <TopNav />

      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_10%,rgba(255,215,0,0.14),transparent_35%),radial-gradient(circle_at_88%_80%,rgba(88,120,255,0.22),transparent_40%),linear-gradient(145deg,#05081c,#0a1740_38%,#201545_68%,#060718_100%)]" />

      <motion.div
        aria-hidden
        className="pointer-events-none absolute -top-24 left-1/2 h-[22rem] w-[22rem] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(255,215,0,0.22),rgba(255,215,0,0))] blur-2xl [transform:translateZ(0)] [will-change:transform]"
        animate={{ x: [-18, 18, -18], y: [0, 16, 0] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.div
        aria-hidden
        className="pointer-events-none absolute right-20 top-40 h-24 w-24 rounded-full bg-accent/30 blur-xl [transform:translateZ(0)] [will-change:transform]"
        animate={{ x: [0, 16, 0], y: [0, -14, 0], opacity: [0.45, 0.8, 0.45] }}
        transition={{ duration: 9, repeat: Infinity, ease: "easeInOut" }}
      />

      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {Array.from({ length: 10 }).map((_, i) => (
          <motion.span
            key={`star-${i}`}
            className="absolute h-1 w-1 rounded-full bg-accent/70"
            style={{
              left: `${(i * 37) % 100}%`,
              top: `${(i * 23 + 11) % 100}%`,
            }}
            animate={{ opacity: [0.12, 0.8, 0.12], scale: [0.85, 1.35, 0.85] }}
            transition={{ duration: 5 + (i % 4), repeat: Infinity, delay: i * 0.28, ease: "easeInOut" }}
          />
        ))}
      </div>

      <div className="pointer-events-none absolute inset-0 opacity-50 [mask-image:radial-gradient(circle_at_center,black,transparent_75%)]">
        <div className="absolute left-1/4 top-28 h-56 w-56 animate-pulse rounded-full bg-accent/10 blur-3xl" />
        <div className="absolute bottom-20 right-16 h-64 w-64 animate-pulse rounded-full bg-primary/40 blur-3xl [animation-delay:450ms]" />
      </div>

      <div className="relative mx-auto flex w-full max-w-6xl flex-col gap-20 px-5 pb-24 pt-12 sm:px-8 lg:gap-24 lg:px-12">
        <section className="relative rounded-3xl border border-border/60 bg-card/55 p-7 shadow-halo backdrop-blur-xl transition duration-500 hover:border-accent/35 sm:p-10">
          <div className="pointer-events-none absolute inset-0 rounded-3xl bg-[radial-gradient(circle_at_15%_20%,rgba(255,215,0,0.14),transparent_45%)]" />
          <p className="text-xs uppercase tracking-[0.28em] text-accent/85">GitaGPT Mentor</p>
          <h1 className="mt-3 text-4xl font-semibold leading-tight font-[var(--font-heading)] sm:text-5xl lg:text-6xl">
            AI-Powered Dharmic Decision Intelligence
          </h1>
          <p className="mt-6 max-w-4xl text-base leading-8 text-muted-foreground sm:text-lg">
            GitaGPT Mentor combines AI, Retrieval-Augmented Generation, Bhagavad Gita wisdom, and contextual human
            understanding to guide users through anxiety, overthinking, career confusion, relationships, and moral
            dilemmas.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link
              href="/chat"
              className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-accent-foreground transition hover:translate-y-[-1px] hover:bg-accent/90"
            >
              Start Your Journey
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="#support"
              className="inline-flex items-center rounded-xl border border-border/80 bg-background/45 px-5 py-3 text-sm font-semibold text-foreground transition hover:border-accent/40 hover:text-accent"
            >
              Support GitaGPT
            </Link>
          </div>
        </section>

        <section>
          <div className="mb-6">
            <p className="text-xs uppercase tracking-[0.22em] text-accent/90">Proof and Impact</p>
            <h2 className="mt-2 text-3xl font-semibold font-[var(--font-heading)] sm:text-4xl">
              Trusted Guidance, Powered by AI
            </h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {stats.map((stat) => (
              <CountUpStat key={stat.label} value={stat.value} suffix={stat.suffix} label={stat.label} />
            ))}
          </div>
        </section>

        <section>
          <h2 className="text-3xl font-semibold font-[var(--font-heading)] sm:text-4xl">
            Testimonials
          </h2>
          <div className="mt-8 grid gap-4 lg:grid-cols-3">
            {testimonials.map((quote) => (
              <article
                key={quote}
                className="rounded-2xl border border-border/70 bg-card/60 p-6 backdrop-blur-md transition duration-300 hover:-translate-y-1 hover:scale-[1.01] hover:border-accent/50 hover:shadow-halo"
              >
                <p className="text-base leading-8 text-foreground/90">&ldquo;{quote}&rdquo;</p>
              </article>
            ))}
          </div>
        </section>

        <section className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <article className="rounded-3xl border border-border/70 bg-card/55 p-7 backdrop-blur-xl transition duration-500 hover:-translate-y-1 hover:scale-[1.01] hover:border-accent/40 hover:shadow-halo sm:p-9">
            <h2 className="text-3xl font-semibold font-[var(--font-heading)] sm:text-4xl">What is GitaGPT?</h2>
            <p className="mt-5 text-base leading-8 text-muted-foreground">
              GitaGPT Mentor combines modern AI with Retrieval-Augmented Generation (RAG), Bhagavad Gita wisdom,
              and contextual understanding of human situations. The goal is simple: deliver practical, spiritually
              grounded guidance that helps people make clearer decisions in moments that matter.
            </p>
          </article>
          <article className="rounded-3xl border border-border/70 bg-background/55 p-7 backdrop-blur-xl transition duration-500 hover:-translate-y-1 hover:scale-[1.01] hover:border-accent/40 hover:shadow-halo sm:p-9">
            <h3 className="text-sm uppercase tracking-[0.2em] text-accent/85">Core Stack</h3>
            <ul className="mt-5 space-y-3 text-muted-foreground">
              <li className="flex items-center gap-3"><GitBranch className="h-4 w-4 text-accent" /> AI + RAG architecture</li>
              <li className="flex items-center gap-3"><Sparkles className="h-4 w-4 text-accent" /> Bhagavad Gita grounding</li>
              <li className="flex items-center gap-3"><BrainCircuit className="h-4 w-4 text-accent" /> Context-aware reasoning</li>
              <li className="flex items-center gap-3"><HeartHandshake className="h-4 w-4 text-accent" /> Human-centric guidance</li>
            </ul>
          </article>
        </section>

        <section>
          <h2 className="text-3xl font-semibold font-[var(--font-heading)] sm:text-4xl">Key Features</h2>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {features.map(({ title, description, icon: Icon }) => (
              <article
                key={title}
                className="group rounded-2xl border border-border/70 bg-card/60 p-6 backdrop-blur transition duration-300 hover:-translate-y-1 hover:scale-[1.02] hover:border-accent/55 hover:shadow-halo"
              >
                <div className="inline-flex rounded-lg border border-accent/35 bg-accent/10 p-2 text-accent transition group-hover:scale-105">
                  <Icon className="h-4 w-4" />
                </div>
                <h3 className="mt-4 text-lg font-semibold text-foreground">{title}</h3>
                <p className="mt-3 text-sm leading-7 text-muted-foreground">{description}</p>
              </article>
            ))}
          </div>
        </section>

        <section>
          <h2 className="text-3xl font-semibold font-[var(--font-heading)] sm:text-4xl">
            Helping People Through Real-Life Battles
          </h2>
          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            {scenarios.map((scenario) => (
              <article
                key={scenario.title}
                className="rounded-2xl border border-border/70 bg-card/60 p-6 backdrop-blur transition duration-300 hover:-translate-y-1 hover:scale-[1.01] hover:border-accent/45 hover:shadow-halo"
              >
                <h3 className="text-lg font-semibold text-foreground">{scenario.title}</h3>
                <p className="mt-3 text-sm leading-7 text-muted-foreground">{scenario.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="rounded-3xl border border-border/70 bg-card/55 p-7 backdrop-blur-xl transition duration-500 hover:border-accent/35 sm:p-10">
          <h2 className="text-3xl font-semibold font-[var(--font-heading)] sm:text-4xl">Meet the Developer</h2>
          <p className="mt-5 max-w-4xl text-base leading-8 text-muted-foreground">
            Built by Pavan Sai, an AI Engineer passionate about building AI systems that solve meaningful
            real-world problems.
          </p>
          <p className="mt-4 text-base leading-8 text-muted-foreground">
            If you&apos;d like to contribute to GitaGPT Mentor, feel free to visit the GitHub repository and contribute.
          </p>

          <div className="mt-7 flex flex-wrap gap-3">
            <a
              href="https://linkedin.com/in/pavans-ai25/"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-xl border border-border/75 bg-background/60 px-4 py-2.5 text-sm font-medium transition hover:border-accent/45 hover:text-accent"
            >
              <Linkedin className="h-4 w-4" /> LinkedIn
            </a>
            <a
              href="https://github.com/PavansaiBheemisetty"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-xl border border-border/75 bg-background/60 px-4 py-2.5 text-sm font-medium transition hover:border-accent/45 hover:text-accent"
            >
              <Github className="h-4 w-4" /> GitHub
            </a>
            <a
              href="https://github.com/PavansaiBheemisetty/GitaGPT-Mentor"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-xl border border-border/75 bg-background/60 px-4 py-2.5 text-sm font-medium transition hover:border-accent/45 hover:text-accent"
            >
              <GitBranch className="h-4 w-4" /> Project Repository
            </a>
          </div>

          <div className="mt-7 grid gap-3 text-sm text-muted-foreground sm:grid-cols-2">
            <a href="mailto:pavansai.bheemisetty@gmail.com" className="inline-flex items-center gap-2 transition hover:text-accent">
              <Mail className="h-4 w-4 text-accent" /> pavansai.bheemisetty@gmail.com
            </a>
            <a href="tel:+917731911449" className="inline-flex items-center gap-2 transition hover:text-accent">
              <Phone className="h-4 w-4 text-accent" /> +91 7731911449
            </a>
          </div>
        </section>

        <section id="support" className="rounded-3xl border border-border/70 bg-background/55 p-7 backdrop-blur-xl transition duration-500 hover:border-accent/35 sm:p-10">
          <h2 className="text-3xl font-semibold font-[var(--font-heading)] sm:text-4xl">Keep GitaGPT Running ❤️</h2>
          <p className="mt-5 max-w-3xl text-base leading-8 text-muted-foreground">
            Running AI systems and maintaining infrastructure costs money.
          </p>
          <p className="mt-3 max-w-3xl text-base leading-8 text-muted-foreground">
            Your support helps keep GitaGPT free and continuously improving.
          </p>

          <div className="mt-7 grid gap-5 lg:grid-cols-[280px_1fr]">
            <div className="rounded-2xl border border-accent/30 bg-card/50 p-4 backdrop-blur-md">
              <div className="mx-auto grid h-56 w-56 grid-cols-8 gap-1 rounded-xl border border-border/60 bg-background/80 p-3">
                {Array.from({ length: 64 }).map((_, i) => (
                  <div
                    key={`qr-${i}`}
                    className={`${(i * 7 + 3) % 5 === 0 || (i % 11 === 0) ? "bg-foreground/85" : "bg-foreground/10"} rounded-[2px]`}
                  />
                ))}
              </div>
              <p className="mt-3 text-center text-xs uppercase tracking-[0.18em] text-accent/85">Scan to Donate via UPI</p>
            </div>

            <div className="rounded-2xl border border-border/70 bg-card/45 p-5 backdrop-blur-md">
              <p className="text-sm uppercase tracking-[0.16em] text-accent/85">UPI ID</p>
              <p className="mt-2 text-lg font-semibold">{upiId}</p>
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={copyUpiId}
                  className="inline-flex items-center gap-2 rounded-xl border border-border/80 bg-background/50 px-4 py-2.5 text-sm font-medium transition hover:border-accent/45 hover:text-accent"
                >
                  {copied ? "Copied" : "Copy UPI ID"}
                </button>
                {isMobile ? (
                  <a
                    href="upi://pay?pa=7731911449@slc&pn=Pavan%20Sai&cu=INR"
                    className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-accent-foreground transition hover:bg-accent/90"
                  >
                    Open in UPI App
                    <HeartHandshake className="h-4 w-4" />
                  </a>
                ) : null}
              </div>
            </div>
          </div>
        </section>

        <section className="relative overflow-hidden rounded-3xl border border-accent/45 bg-[linear-gradient(135deg,rgba(255,215,0,0.14),rgba(255,215,0,0.03)_40%,rgba(10,16,39,0.72))] p-7 shadow-halo backdrop-blur-xl sm:p-10">
          <motion.div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[linear-gradient(110deg,rgba(255,215,0,0.08),transparent_35%,rgba(255,215,0,0.08)_65%,transparent)]"
            animate={{ x: ["-35%", "35%"] }}
            transition={{ duration: 8.2, repeat: Infinity, ease: "linear" }}
          />
          <p className="text-xs uppercase tracking-[0.22em] text-accent/90">Dharmic Decision Intelligence</p>
          <h2 className="mt-3 text-3xl font-semibold font-[var(--font-heading)] sm:text-4xl">Begin the conversation that changes your direction.</h2>
          <p className="mt-4 max-w-2xl text-base leading-8 text-muted-foreground">
            Whether you are navigating pressure, doubt, or purpose, GitaGPT Mentor is here to guide your next step.
          </p>
          <Link
            href="/chat"
            className="mt-7 inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-accent-foreground transition hover:translate-y-[-1px] hover:bg-accent/90"
          >
            Start Your Journey
            <ArrowRight className="h-4 w-4" />
          </Link>
        </section>
      </div>
    </main>
  );
}
