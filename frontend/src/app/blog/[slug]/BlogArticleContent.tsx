"use client";

import Link from "next/link";
import { ArrowLeft, ArrowRight, BookOpen, Clock, User } from "lucide-react";
import { motion } from "framer-motion";
import { TopNav } from "../../../components/marketing/TopNav";
import type { BlogPost } from "../../../lib/blog-data";

interface BlogArticleContentProps {
  post: BlogPost;
  relatedPosts: BlogPost[];
}

function renderMarkdown(content: string) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let currentList: string[] = [];
  let listKey = 0;

  const flushList = () => {
    if (currentList.length > 0) {
      elements.push(
        <ul
          key={`list-${listKey++}`}
          className="my-4 space-y-2 pl-5 text-base leading-8 text-muted-foreground"
        >
          {currentList.map((item, i) => (
            <li
              key={i}
              className="flex items-start gap-2 before:mt-[0.55rem] before:inline-block before:h-1.5 before:w-1.5 before:shrink-0 before:rounded-full before:bg-accent/60"
            >
              <span dangerouslySetInnerHTML={{ __html: formatInline(item) }} />
            </li>
          ))}
        </ul>
      );
      currentList = [];
    }
  };

  const formatInline = (text: string) => {
    return text
      .replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>")
      .replace(/\*\*(.+?)\*\*/g, "<strong class='text-foreground font-semibold'>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em class='text-accent/90 italic'>$1</em>");
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed === "") {
      flushList();
      continue;
    }

    if (trimmed.startsWith("### ")) {
      flushList();
      elements.push(
        <h4
          key={`h4-${i}`}
          className="mt-8 mb-3 text-lg font-semibold text-foreground"
        >
          {trimmed.slice(4)}
        </h4>
      );
      continue;
    }

    if (trimmed.startsWith("## ")) {
      flushList();
      elements.push(
        <h3
          key={`h3-${i}`}
          className="mt-10 mb-4 text-2xl font-semibold text-foreground font-[var(--font-heading)]"
        >
          {trimmed.slice(3)}
        </h3>
      );
      continue;
    }

    if (trimmed.startsWith("- ")) {
      currentList.push(trimmed.slice(2));
      continue;
    }

    if (/^\d+\.\s/.test(trimmed)) {
      currentList.push(trimmed.replace(/^\d+\.\s/, ""));
      continue;
    }

    flushList();
    elements.push(
      <p
        key={`p-${i}`}
        className="my-4 text-base leading-8 text-muted-foreground"
        dangerouslySetInnerHTML={{ __html: formatInline(trimmed) }}
      />
    );
  }

  flushList();
  return elements;
}

export function BlogArticleContent({
  post,
  relatedPosts,
}: BlogArticleContentProps) {
  return (
    <main className="relative min-h-screen bg-background text-foreground">
      <TopNav />

      {/* Background */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background: `${post.heroGradient}, linear-gradient(145deg,#05081c,#0a1740 38%,#201545 68%,#060718 100%)`,
        }}
      />

      {/* Floating orbs */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -top-24 left-1/2 h-[22rem] w-[22rem] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(255,215,0,0.18),rgba(255,215,0,0))] blur-2xl [transform:translateZ(0)] [will-change:transform]"
        animate={{ x: [-18, 18, -18], y: [0, 16, 0] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
      />

      <article className="relative mx-auto max-w-4xl px-5 pb-24 pt-14 sm:px-8">
        {/* Back link */}
        <Link
          href="/blog"
          className="mb-8 inline-flex items-center gap-2 text-sm text-muted-foreground transition hover:text-accent"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Blog
        </Link>

        {/* Hero section */}
        <motion.header
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="rounded-3xl border border-border/70 bg-card/55 p-8 shadow-[0_8px_48px_rgba(255,215,0,0.05)] backdrop-blur-xl sm:p-12"
        >
          <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-accent/80" />
              {post.readTime}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <User className="h-3.5 w-3.5 text-accent/80" />
              {post.author}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <BookOpen className="h-3.5 w-3.5 text-accent/80" />
              {post.date}
            </span>
          </div>

          <h1 className="mt-5 text-3xl font-semibold leading-tight font-[var(--font-heading)] sm:text-4xl lg:text-5xl">
            {post.title}
          </h1>

          <p className="mt-5 text-base leading-8 text-muted-foreground sm:text-lg">
            {post.summary}
          </p>
        </motion.header>

        {/* Article body */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15, ease: "easeOut" }}
          className="mt-10 rounded-3xl border border-border/60 bg-card/40 p-8 backdrop-blur-md sm:p-12"
        >
          <div className="markdown-content">{renderMarkdown(post.content)}</div>
        </motion.div>

        {/* Related posts */}
        {relatedPosts.length > 0 && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3, ease: "easeOut" }}
            className="mt-14"
          >
            <p className="text-xs uppercase tracking-[0.22em] text-accent/90">
              Continue Reading
            </p>
            <h2 className="mt-2 text-2xl font-semibold font-[var(--font-heading)] sm:text-3xl">
              Related Articles
            </h2>

            <div className="mt-6 grid gap-4 md:grid-cols-3">
              {relatedPosts.map((related) => (
                <Link
                  key={related.slug}
                  href={`/blog/${related.slug}`}
                  className="group rounded-2xl border border-border/70 bg-card/60 p-6 backdrop-blur-md transition duration-300 hover:-translate-y-1 hover:scale-[1.01] hover:border-accent/50 hover:shadow-[0_8px_32px_rgba(255,215,0,0.06)]"
                >
                  <h3 className="text-lg font-semibold leading-7 transition group-hover:text-accent">
                    {related.title}
                  </h3>
                  <p className="mt-3 line-clamp-2 text-sm leading-7 text-muted-foreground">
                    {related.summary}
                  </p>
                  <div className="mt-4 flex items-center justify-between">
                    <span className="text-xs text-accent/70">
                      {related.readTime}
                    </span>
                    <ArrowRight className="h-4 w-4 text-muted-foreground transition group-hover:text-accent" />
                  </div>
                </Link>
              ))}
            </div>
          </motion.section>
        )}
      </article>
    </main>
  );
}
