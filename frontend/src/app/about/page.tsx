import type { Metadata } from "next";
import { AboutPageContent } from "../../components/about/AboutPageContent";

export const metadata: Metadata = {
  title: "About | GitaGPT Mentor",
  description:
    "Learn about GitaGPT Mentor, the AI-powered Bhagavad Gita assistant built to guide people through real-life challenges.",
  alternates: {
    canonical: "https://gitagpt.tech/about",
  },
  openGraph: {
    title: "About | GitaGPT Mentor",
    description:
      "Learn about GitaGPT Mentor, the AI-powered Bhagavad Gita assistant built to guide people through real-life challenges.",
    url: "https://gitagpt.tech/about",
    type: "article",
  },
};

export default function AboutPage() {
  return <AboutPageContent />;
}
