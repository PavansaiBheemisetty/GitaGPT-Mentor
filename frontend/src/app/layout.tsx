import "./globals.css";
import type { Metadata, Viewport } from "next";
import { Cinzel, Inter } from "next/font/google";
import { SpeedInsights } from '@vercel/speed-insights/next';
import { Analytics } from '@vercel/analytics/next';

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-body",
});

const cinzel = Cinzel({
  subsets: ["latin"],
  variable: "--font-heading",
  weight: ["400", "600", "700"],
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
};

export const metadata: Metadata = {
  metadataBase: new URL("https://gitagpt.tech"),
  title: {
    default: "GitaGPT — Divine Guidance",
    template: "%s | GitaGPT",
  },
  description:
    "A Krishna-inspired AI mentor grounded in Bhagavad Gita teachings to guide you through life, purpose, and inner conflict.",
  applicationName: "GitaGPT",
  alternates: {
    canonical: "https://gitagpt.tech",
  },
  icons: {
    icon: [
      { url: "/favicon.ico" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
  manifest: "/manifest.webmanifest",
  openGraph: {
    title: "GitaGPT — Ancient Wisdom. Modern Clarity.",
    description:
      "A Krishna-inspired AI mentor grounded in Bhagavad Gita teachings to guide you through life, purpose, and inner conflict.",
    url: "https://gitagpt.tech",
    siteName: "GitaGPT",
    type: "website",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "GitaGPT - Ancient Wisdom. Modern Clarity.",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "GitaGPT — Ancient Wisdom. Modern Clarity.",
    description:
      "A Krishna-inspired AI mentor grounded in Bhagavad Gita teachings to guide you through life, purpose, and inner conflict.",
    images: ["/og-image.png"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${cinzel.variable} h-full overflow-hidden font-[var(--font-body)]`}>
        {children}
        <SpeedInsights />
        <Analytics />
      </body>
    </html>
  );
}
