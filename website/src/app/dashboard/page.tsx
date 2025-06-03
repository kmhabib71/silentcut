"use client";

import { useSession, signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Download, Settings, LogOut, User, Clock, Zap } from "lucide-react";

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/auth/signin");
    }
  }, [status, router]);

  if (status === "loading") {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="text-white text-xl">Loading...</div>
      </div>
    );
  }

  if (!session) {
    return null;
  }

  const handleSignOut = () => {
    signOut({ callbackUrl: "/" });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Navigation */}
      <nav className="bg-black/20 backdrop-blur-md border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <Link href="/" className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
                <Zap className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-white">
                SilenceCutter
              </span>
            </Link>

            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 bg-gray-600 rounded-full flex items-center justify-center">
                  {session.user?.image ? (
                    <img
                      src={session.user.image}
                      alt="Profile"
                      className="w-8 h-8 rounded-full"
                    />
                  ) : (
                    <User className="w-4 h-4 text-white" />
                  )}
                </div>
                <span className="text-white text-sm">
                  {session.user?.name || session.user?.email}
                </span>
              </div>

              <button
                onClick={handleSignOut}
                className="flex items-center space-x-2 text-gray-300 hover:text-white transition-colors"
              >
                <LogOut className="w-4 h-4" />
                <span>Sign Out</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
        >
          {/* Welcome Header */}
          <div className="text-center mb-12">
            <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
              Welcome to SilenceCutter
            </h1>
            <p className="text-xl text-gray-300 max-w-2xl mx-auto">
              Your professional silence removal tool is ready to use. Download
              the desktop application to get started.
            </p>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6">
              <div className="flex items-center space-x-3 mb-3">
                <Clock className="w-6 h-6 text-purple-400" />
                <h3 className="text-lg font-semibold text-white">
                  Usage This Month
                </h3>
              </div>
              <p className="text-3xl font-bold text-white">0 min</p>
              <p className="text-sm text-gray-400">of 60 minutes available</p>
            </div>

            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6">
              <div className="flex items-center space-x-3 mb-3">
                <Zap className="w-6 h-6 text-green-400" />
                <h3 className="text-lg font-semibold text-white">
                  Files Processed
                </h3>
              </div>
              <p className="text-3xl font-bold text-white">0</p>
              <p className="text-sm text-gray-400">total files processed</p>
            </div>

            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6">
              <div className="flex items-center space-x-3 mb-3">
                <User className="w-6 h-6 text-blue-400" />
                <h3 className="text-lg font-semibold text-white">Plan</h3>
              </div>
              <p className="text-3xl font-bold text-white">Free</p>
              <Link
                href="/pricing"
                className="text-sm text-purple-400 hover:text-purple-300"
              >
                Upgrade to Pro
              </Link>
            </div>
          </div>

          {/* Download Section */}
          <div className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-xl p-8 mb-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg flex items-center justify-center mx-auto mb-4">
                <Download className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-white mb-3">
                Download SilenceCutter Desktop
              </h2>
              <p className="text-gray-300 mb-6 max-w-2xl mx-auto">
                Get the full-featured desktop application that integrates with
                your account. Process unlimited files with advanced features and
                batch processing.
              </p>

              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <button className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-8 py-3 rounded-lg font-semibold hover:from-purple-600 hover:to-pink-600 transition-all transform hover:scale-105 flex items-center justify-center space-x-2">
                  <Download className="w-5 h-5" />
                  <span>Download for Windows</span>
                </button>

                <button className="border border-white/20 text-white px-8 py-3 rounded-lg font-semibold hover:bg-white/10 transition-all flex items-center justify-center space-x-2">
                  <span>View Tutorial</span>
                </button>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6">
              <h3 className="text-xl font-semibold text-white mb-4">
                Quick Actions
              </h3>
              <div className="space-y-3">
                <Link
                  href="/tutorial"
                  className="block p-3 rounded-lg border border-white/10 hover:bg-white/5 transition-colors"
                >
                  <div className="text-white font-medium">
                    📚 Watch Tutorial
                  </div>
                  <div className="text-gray-400 text-sm">
                    Learn how to use SilenceCutter effectively
                  </div>
                </Link>

                <Link
                  href="/pricing"
                  className="block p-3 rounded-lg border border-white/10 hover:bg-white/5 transition-colors"
                >
                  <div className="text-white font-medium">🚀 Upgrade Plan</div>
                  <div className="text-gray-400 text-sm">
                    Unlock unlimited processing and advanced features
                  </div>
                </Link>

                <Link
                  href="/settings"
                  className="block p-3 rounded-lg border border-white/10 hover:bg-white/5 transition-colors"
                >
                  <div className="text-white font-medium">
                    ⚙️ Account Settings
                  </div>
                  <div className="text-gray-400 text-sm">
                    Manage your account and preferences
                  </div>
                </Link>
              </div>
            </div>

            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6">
              <h3 className="text-xl font-semibold text-white mb-4">
                Recent Activity
              </h3>
              <div className="text-center py-8">
                <div className="text-gray-400 mb-2">No recent activity</div>
                <div className="text-gray-500 text-sm">
                  Your processed files will appear here
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
