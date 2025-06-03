"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Users,
  Crown,
  Ban,
  CheckCircle,
  XCircle,
  TrendingUp,
  DollarSign,
  Clock,
  Search,
  Filter,
  MoreVertical,
  Edit,
  Trash2,
  Shield,
  Monitor,
  UserX,
  Globe,
} from "lucide-react";

interface User {
  _id: string;
  email: string;
  name: string;
  subscription: {
    plan: "free" | "monthly" | "yearly";
    status: "active" | "cancelled" | "expired";
    startDate: string;
    endDate?: string;
  };
  usage: {
    totalMinutesUsed: number;
    monthlyUsage: { month: string; minutes: number }[];
  };
  banned: boolean;
  isAdmin: boolean;
  createdAt: string;
  emailVerified: boolean;
}

interface AnonymousSession {
  id: string;
  sessionId: string;
  permanentId: string;
  deviceName: string;
  linkedEmail: string | null;
  totalMinutesUsed: number;
  filesProcessed: number;
  firstUseDate: string;
  lastUseDate: string;
  ipAddress: string;
  userAgent: string;
  registeredOnline: boolean;
  syncedToUser: string | null;
  files: Array<{
    fileName: string;
    durationMinutes: number;
    processedDate: string;
  }>;
  createdAt: string;
  updatedAt: string;
}

export default function AdminPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [anonymousSessions, setAnonymousSessions] = useState<
    AnonymousSession[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"users" | "anonymous">("users");
  const [searchTerm, setSearchTerm] = useState("");
  const [filterPlan, setFilterPlan] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [stats, setStats] = useState({
    totalUsers: 0,
    activeSubscriptions: 0,
    totalRevenue: 0,
    totalMinutesProcessed: 0,
    analytics: {
      users: {
        total: 0,
        banned: 0,
        verified: 0,
        newLast30Days: 0,
        avgMinutesPerUser: 0,
      },
      anonymousSessions: {
        total: 0,
        totalMinutesProcessed: 0,
        totalFilesProcessed: 0,
        avgMinutesPerSession: 0,
        newLast30Days: 0,
      },
      subscriptions: {
        active: 0,
        totalRevenue: 0,
        planDistribution: {},
      },
      usage: {
        totalMinutesProcessed: 0,
        registeredUserMinutes: 0,
        anonymousUserMinutes: 0,
        topUsers: [],
      },
      activity: {
        recentActivity: [],
        systemHealth: {
          totalSessions: 0,
          activeUsers: 0,
          anonymousSessions: 0,
          registeredUsers: 0,
          conversionRate: 0,
        },
      },
    },
    tracking: {
      totalUniqueSessions: 0,
      lastUpdate: "",
      dataPoints: {
        registeredUsers: 0,
        anonymousSessions: 0,
        totalInteractions: 0,
      },
    },
  });

  // Redirect if not admin
  useEffect(() => {
    if (status === "loading") return;
    if (!session || !session.user?.isAdmin) {
      router.push("/");
      return;
    }
    fetchUsers();
    fetchAnonymousSessions();
    fetchStats();
  }, [session, status, router]);

  const fetchUsers = async () => {
    try {
      const response = await fetch("/api/admin/users");
      if (response.ok) {
        const data = await response.json();
        setUsers(data.users);
      }
    } catch (error) {
      console.error("Failed to fetch users:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAnonymousSessions = async () => {
    try {
      const response = await fetch("/api/admin/anonymous-sessions");
      if (response.ok) {
        const data = await response.json();
        setAnonymousSessions(data.sessions);
      }
    } catch (error) {
      console.error("Failed to fetch anonymous sessions:", error);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch("/api/admin/stats");
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    }
  };

  const handleBanUser = async (userId: string, banned: boolean) => {
    try {
      const response = await fetch("/api/admin/users/ban", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId, banned }),
      });

      if (response.ok) {
        setUsers(
          users.map((user) =>
            user._id === userId ? { ...user, banned } : user
          )
        );
      }
    } catch (error) {
      console.error("Failed to update user ban status:", error);
    }
  };

  const handleUpdateSubscription = async (
    userId: string,
    plan: string,
    status: string
  ) => {
    try {
      const response = await fetch("/api/admin/users/subscription", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId, plan, status }),
      });

      if (response.ok) {
        setUsers(
          users.map((user) =>
            user._id === userId
              ? {
                  ...user,
                  subscription: {
                    ...user.subscription,
                    plan: plan as any,
                    status: status as any,
                  },
                }
              : user
          )
        );
      }
    } catch (error) {
      console.error("Failed to update subscription:", error);
    }
  };

  const filteredUsers = users.filter((user) => {
    const matchesSearch =
      user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      user.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesPlan =
      filterPlan === "all" || user.subscription.plan === filterPlan;
    const matchesStatus =
      filterStatus === "all" || user.subscription.status === filterStatus;

    return matchesSearch && matchesPlan && matchesStatus;
  });

  const filteredAnonymousSessions = anonymousSessions.filter((session) => {
    const matchesSearch =
      session.sessionId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      session.permanentId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      session.deviceName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (session.linkedEmail &&
        session.linkedEmail.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (session.ipAddress && session.ipAddress.includes(searchTerm));

    return matchesSearch;
  });

  if (status === "loading" || loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="text-white text-xl">Loading...</div>
      </div>
    );
  }

  if (!session?.user?.isAdmin) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Header */}
      <div className="bg-black/20 backdrop-blur-md border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Shield className="w-8 h-8 text-purple-400" />
              <h1 className="text-2xl font-bold text-white">Admin Dashboard</h1>
            </div>
            <div className="text-gray-300">Welcome, {session.user.name}</div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Total Users</p>
                <p className="text-2xl font-bold text-white">
                  {stats.totalUsers}
                </p>
                <p className="text-green-400 text-xs mt-1">
                  +{stats.analytics.users.newLast30Days} this month
                </p>
              </div>
              <Users className="w-8 h-8 text-blue-400" />
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Active Subscriptions</p>
                <p className="text-2xl font-bold text-white">
                  {stats.activeSubscriptions}
                </p>
                <p className="text-blue-400 text-xs mt-1">
                  {stats.analytics.activity.systemHealth.conversionRate}%
                  conversion
                </p>
              </div>
              <Crown className="w-8 h-8 text-yellow-400" />
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Total Revenue</p>
                <p className="text-2xl font-bold text-white">
                  ${stats.totalRevenue}
                </p>
                <p className="text-green-400 text-xs mt-1">Monthly recurring</p>
              </div>
              <DollarSign className="w-8 h-8 text-green-400" />
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Minutes Processed</p>
                <p className="text-2xl font-bold text-white">
                  {stats.totalMinutesProcessed.toLocaleString()}
                </p>
                <p className="text-purple-400 text-xs mt-1">
                  {Math.ceil(stats.analytics.usage.anonymousUserMinutes)}min
                  anonymous
                </p>
              </div>
              <Clock className="w-8 h-8 text-purple-400" />
            </div>
          </motion.div>
        </div>

        {/* Additional Analytics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">
                Anonymous Sessions
              </h3>
              <TrendingUp className="w-6 h-6 text-cyan-400" />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-400">Total Sessions:</span>
                <span className="text-white font-medium">
                  {stats.analytics.anonymousSessions.total}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Avg Minutes/Session:</span>
                <span className="text-white font-medium">
                  {stats.analytics.anonymousSessions.avgMinutesPerSession.toFixed(
                    1
                  )}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">New This Month:</span>
                <span className="text-green-400 font-medium">
                  +{stats.analytics.anonymousSessions.newLast30Days}
                </span>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">
                Unique Identifiers
              </h3>
              <Shield className="w-6 h-6 text-purple-400" />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-400">Total Sessions:</span>
                <span className="text-white font-medium">
                  {stats.tracking.totalUniqueSessions}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Interactions:</span>
                <span className="text-white font-medium">
                  {stats.tracking.dataPoints.totalInteractions}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Last Update:</span>
                <span className="text-gray-300 text-sm">
                  {new Date(stats.tracking.lastUpdate).toLocaleTimeString()}
                </span>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">
                System Health
              </h3>
              <CheckCircle className="w-6 h-6 text-green-400" />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-400">Active Users:</span>
                <span className="text-green-400 font-medium">
                  {stats.analytics.activity.systemHealth.activeUsers}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Conversion Rate:</span>
                <span className="text-blue-400 font-medium">
                  {stats.analytics.activity.systemHealth.conversionRate}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Verified Users:</span>
                <span className="text-white font-medium">
                  {stats.analytics.users.verified}
                </span>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Tab Navigation */}
        <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl mb-8">
          <div className="flex border-b border-white/10">
            <button
              onClick={() => setActiveTab("users")}
              className={`flex-1 px-6 py-4 text-sm font-medium transition-colors ${
                activeTab === "users"
                  ? "text-white bg-white/10 border-b-2 border-purple-400"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              <div className="flex items-center justify-center space-x-2">
                <Users className="w-4 h-4" />
                <span>Registered Users ({users.length})</span>
              </div>
            </button>
            <button
              onClick={() => setActiveTab("anonymous")}
              className={`flex-1 px-6 py-4 text-sm font-medium transition-colors ${
                activeTab === "anonymous"
                  ? "text-white bg-white/10 border-b-2 border-purple-400"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              <div className="flex items-center justify-center space-x-2">
                <Monitor className="w-4 h-4" />
                <span>Anonymous Sessions ({anonymousSessions.length})</span>
              </div>
            </button>
          </div>

          {/* Filters */}
          <div className="p-6">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="text"
                    placeholder={
                      activeTab === "users"
                        ? "Search users..."
                        : "Search sessions, devices, emails..."
                    }
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
              </div>

              {activeTab === "users" && (
                <>
                  <select
                    value={filterPlan}
                    onChange={(e) => setFilterPlan(e.target.value)}
                    className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="all">All Plans</option>
                    <option value="free">Free</option>
                    <option value="monthly">Monthly</option>
                    <option value="yearly">Yearly</option>
                  </select>

                  <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="all">All Status</option>
                    <option value="active">Active</option>
                    <option value="cancelled">Cancelled</option>
                    <option value="expired">Expired</option>
                  </select>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Content based on active tab */}
        {activeTab === "users" ? (
          /* Users Table */
          <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-white/5 border-b border-white/10">
                  <tr>
                    <th className="px-6 py-4 text-left text-sm font-medium text-gray-300">
                      User
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-medium text-gray-300">
                      Plan
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-medium text-gray-300">
                      Status
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-medium text-gray-300">
                      Usage
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-medium text-gray-300">
                      Joined
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-medium text-gray-300">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filteredUsers.map((user) => (
                    <tr key={user._id} className="hover:bg-white/5">
                      <td className="px-6 py-4">
                        <div className="flex items-center space-x-3">
                          <div className="w-8 h-8 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full flex items-center justify-center">
                            <span className="text-white text-sm font-medium">
                              {user.name.charAt(0).toUpperCase()}
                            </span>
                          </div>
                          <div>
                            <div className="text-white font-medium">
                              {user.name}
                            </div>
                            <div className="text-gray-400 text-sm">
                              {user.email}
                            </div>
                            {user.banned && (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-400 mt-1">
                                <Ban className="w-3 h-3 mr-1" />
                                Banned
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                            user.subscription.plan === "free"
                              ? "bg-gray-500/10 text-gray-400"
                              : user.subscription.plan === "monthly"
                              ? "bg-blue-500/10 text-blue-400"
                              : "bg-yellow-500/10 text-yellow-400"
                          }`}
                        >
                          {user.subscription.plan.charAt(0).toUpperCase() +
                            user.subscription.plan.slice(1)}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                            user.subscription.status === "active"
                              ? "bg-green-500/10 text-green-400"
                              : user.subscription.status === "cancelled"
                              ? "bg-yellow-500/10 text-yellow-400"
                              : "bg-red-500/10 text-red-400"
                          }`}
                        >
                          {user.subscription.status === "active" && (
                            <CheckCircle className="w-3 h-3 mr-1" />
                          )}
                          {user.subscription.status === "cancelled" && (
                            <XCircle className="w-3 h-3 mr-1" />
                          )}
                          {user.subscription.status === "expired" && (
                            <XCircle className="w-3 h-3 mr-1" />
                          )}
                          {user.subscription.status.charAt(0).toUpperCase() +
                            user.subscription.status.slice(1)}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-white text-sm">
                          {user.usage.totalMinutesUsed.toFixed(1)} min
                        </div>
                        <div className="text-gray-400 text-xs">
                          Total processed
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-gray-300 text-sm">
                          {new Date(user.createdAt).toLocaleDateString()}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() =>
                              handleBanUser(user._id, !user.banned)
                            }
                            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                              user.banned
                                ? "bg-green-500/10 text-green-400 hover:bg-green-500/20"
                                : "bg-red-500/10 text-red-400 hover:bg-red-500/20"
                            }`}
                          >
                            {user.banned ? "Unban" : "Ban"}
                          </button>

                          <select
                            value={user.subscription.plan}
                            onChange={(e) =>
                              handleUpdateSubscription(
                                user._id,
                                e.target.value,
                                user.subscription.status
                              )
                            }
                            className="px-2 py-1 bg-white/5 border border-white/10 rounded text-xs text-white focus:outline-none focus:ring-1 focus:ring-purple-500"
                          >
                            <option value="free">Free</option>
                            <option value="monthly">Monthly</option>
                            <option value="yearly">Yearly</option>
                          </select>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {filteredUsers.length === 0 && (
              <div className="text-center py-12">
                <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-400">
                  No users found matching your criteria.
                </p>
              </div>
            )}
          </div>
        ) : (
          /* Anonymous Sessions Table */
          <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-white/5 border-b border-white/10">
                  <tr>
                    <th className="px-6 py-4 text-left text-sm font-medium text-gray-300">
                      Device / Session
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-medium text-gray-300">
                      Status
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-medium text-gray-300">
                      Usage
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-medium text-gray-300">
                      Location
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-medium text-gray-300">
                      Last Active
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filteredAnonymousSessions.map((session) => (
                    <tr key={session.id} className="hover:bg-white/5">
                      <td className="px-6 py-4">
                        <div className="flex items-center space-x-3">
                          <div className="w-8 h-8 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full flex items-center justify-center">
                            <Monitor className="w-4 h-4 text-white" />
                          </div>
                          <div>
                            <div className="text-white font-medium">
                              {session.deviceName}
                            </div>
                            <div className="text-gray-400 text-xs">
                              ID: {session.permanentId.slice(0, 8)}...
                            </div>
                            {session.linkedEmail && (
                              <div className="text-blue-400 text-xs">
                                📧 {session.linkedEmail}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="space-y-1">
                          <span
                            className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                              session.registeredOnline
                                ? "bg-green-500/10 text-green-400"
                                : "bg-gray-500/10 text-gray-400"
                            }`}
                          >
                            {session.registeredOnline ? (
                              <Globe className="w-3 h-3 mr-1" />
                            ) : (
                              <UserX className="w-3 h-3 mr-1" />
                            )}
                            {session.registeredOnline ? "Online" : "Offline"}
                          </span>
                          {session.syncedToUser && (
                            <div>
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-500/10 text-purple-400">
                                🔗 Linked to User
                              </span>
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-white text-sm">
                          {session.totalMinutesUsed.toFixed(1)} min
                        </div>
                        <div className="text-gray-400 text-xs">
                          {session.filesProcessed} files processed
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-gray-300 text-sm">
                          {session.ipAddress || "Unknown"}
                        </div>
                        <div className="text-gray-400 text-xs truncate max-w-32">
                          {session.userAgent
                            ? session.userAgent.split(" ")[0]
                            : "Unknown browser"}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-gray-300 text-sm">
                          {new Date(session.lastUseDate).toLocaleDateString()}
                        </div>
                        <div className="text-gray-400 text-xs">
                          {new Date(session.lastUseDate).toLocaleTimeString()}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {filteredAnonymousSessions.length === 0 && (
              <div className="text-center py-12">
                <Monitor className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-400">
                  No anonymous sessions found matching your criteria.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
