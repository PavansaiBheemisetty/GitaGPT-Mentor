import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { blogPosts, getPostBySlug, getAllSlugs } from "../../../lib/blog-data";
import { BlogArticleContent } from "./BlogArticleContent";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  return getAllSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) return { title: "Not Found | GitaGPT" };

  return {
    title: `${post.title} | GitaGPT Blog`,
    description: post.summary,
    alternates: { canonical: `https://gitagpt.tech/blog/${post.slug}` },
    openGraph: {
      title: post.title,
      description: post.summary,
      url: `https://gitagpt.tech/blog/${post.slug}`,
      type: "article",
      publishedTime: post.date,
      authors: [post.author],
    },
    twitter: {
      card: "summary_large_image",
      title: post.title,
      description: post.summary,
    },
  };
}

export default async function BlogPostPage({ params }: PageProps) {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) notFound();

  // Find related posts (all posts except current, take first 3)
  const related = blogPosts.filter((p) => p.slug !== slug).slice(0, 3);

  return <BlogArticleContent post={post} relatedPosts={related} />;
}
