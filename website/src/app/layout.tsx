import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "SilenceCutter - Professional Audio & Video Silence Removal",
  description:
    "Remove silence from audio and video files with AI-powered precision. Perfect for podcasters, YouTubers, and content creators.",
  keywords:
    "silence removal, audio editing, video editing, podcast editing, content creation",
  authors: [{ name: "SilenceCutter Team" }],
  openGraph: {
    title: "SilenceCutter - Professional Audio & Video Silence Removal",
    description:
      "Remove silence from audio and video files with AI-powered precision.",
    type: "website",
    url: "https://silencecutter.com",
  },
  twitter: {
    card: "summary_large_image",
    title: "SilenceCutter - Professional Audio & Video Silence Removal",
    description:
      "Remove silence from audio and video files with AI-powered precision.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
