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

export default function AdminPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterPlan, setFilterPlan] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [stats, setStats] = useState({
    totalUsers: 0,
    activeSubscriptions: 0,
    totalRevenue: 0,
    totalMinutesProcessed: 0,
  });

  // Redirect if not admin
  useEffect(() => {
    if (status === "loading") return;
    if (!session || !session.user?.isAdmin) {
      router.push("/");
      return;
    }
    fetchUsers();
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
              </div>
              <Clock className="w-8 h-8 text-purple-400" />
            </div>
          </motion.div>
        </div>

        {/* Filters */}
        <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6 mb-8">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search users..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>

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
          </div>
        </div>

        {/* Users Table */}
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
                          onClick={() => handleBanUser(user._id, !user.banned)}
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
    </div>
  );
}
