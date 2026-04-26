import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Clock } from "lucide-react";
import { TopNav } from "../../components/marketing/TopNav";
import { blogPosts } from "../../lib/blog-data";

export const metadata: Metadata = {
  title: "Blog | GitaGPT Mentor",
  description:
    "Insights from GitaGPT Mentor on anxiety, career clarity, emotional resilience, and Dharmic decision-making.",
  alternates: { canonical: "https://gitagpt.tech/blog" },
};

export default function BlogPage() {
  return (
    <main className="relative min-h-screen bg-background text-foreground">
      <TopNav />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_10%,rgba(255,215,0,0.12),transparent_35%),radial-gradient(circle_at_88%_80%,rgba(88,120,255,0.20),transparent_40%),linear-gradient(145deg,#05081c,#0a1740_38%,#201545_68%,#060718_100%)]" />

      <section className="relative mx-auto max-w-6xl px-5 pb-20 pt-14 sm:px-8 lg:px-12">
        <p className="text-xs uppercase tracking-[0.24em] text-accent/90">
          GitaGPT Journal
        </p>
        <h1 className="mt-3 text-4xl font-semibold font-[var(--font-heading)] sm:text-5xl">
          Blog
        </h1>
        <p className="mt-4 max-w-3xl text-base leading-8 text-muted-foreground">
          Spiritual intelligence for modern battles, written in a practical
          format for life and work.
        </p>

        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {blogPosts.map((post) => (
            <Link
              key={post.slug}
              href={`/blog/${post.slug}`}
              className="group flex flex-col rounded-2xl border border-border/70 bg-card/60 p-6 backdrop-blur-md transition duration-300 hover:-translate-y-1 hover:scale-[1.01] hover:border-accent/50 hover:shadow-[0_8px_32px_rgba(255,215,0,0.06)]"
            >
              <h2 className="text-xl font-semibold leading-7 transition group-hover:text-accent">
                {post.title}
              </h2>
              <p className="mt-3 flex-1 text-sm leading-7 text-muted-foreground line-clamp-3">
                {post.summary}
              </p>
              <div className="mt-6 flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-xs text-accent/75">
                  <Clock className="h-3.5 w-3.5" />
                  {post.readTime}
                </span>
                <span className="inline-flex items-center gap-1 rounded-xl border border-border/80 bg-background/45 px-3 py-1.5 text-xs font-medium transition group-hover:border-accent/40 group-hover:text-accent">
                  Read
                  <ArrowRight className="h-3 w-3" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
