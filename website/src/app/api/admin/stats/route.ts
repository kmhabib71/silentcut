import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import connectToDatabase from "@/lib/mongodb";
import User from "@/models/User";
import AnonymousSession from "@/models/AnonymousSession";

export async function GET(request: NextRequest) {
  try {
    // Check if user is admin
    const session = await getServerSession(authOptions);
    if (!session?.user?.isAdmin) {
      return NextResponse.json(
        { error: "Admin access required" },
        { status: 403 }
      );
    }

    await connectToDatabase();

    // Get user statistics
    const totalUsers = await User.countDocuments();
    const activeSubscriptions = await User.countDocuments({
      "subscription.status": "active",
      "subscription.plan": { $ne: "free" },
    });

    const bannedUsers = await User.countDocuments({ banned: true });
    const verifiedUsers = await User.countDocuments({ emailVerified: true });

    // Calculate total revenue (simplified - you might want to integrate with actual payment data)
    const paidUsers = await User.find({
      "subscription.plan": { $in: ["monthly", "yearly"] },
      "subscription.status": "active",
    });

    let totalRevenue = 0;
    paidUsers.forEach((user) => {
      if (user.subscription.plan === "monthly") {
        totalRevenue += 9; // $9/month
      } else if (user.subscription.plan === "yearly") {
        totalRevenue += 59; // $59/year
      }
    });

    // Get total minutes processed by registered users
    const userUsageStats = await User.aggregate([
      {
        $group: {
          _id: null,
          totalMinutesProcessed: { $sum: "$usage.totalMinutesUsed" },
          totalFilesProcessed: {
            $sum: {
              $size: {
                $ifNull: ["$usage.monthlyUsage", []],
              },
            },
          },
          avgMinutesPerUser: { $avg: "$usage.totalMinutesUsed" },
        },
      },
    ]);

    // Get anonymous session statistics
    const anonymousStats = await AnonymousSession.getSessionStats();
    const anonymousSessionCount = await AnonymousSession.countDocuments();

    // Get recent activity (last 30 days)
    const recentActivity = await AnonymousSession.getRecentActivity(30);

    // Calculate total usage across all users and anonymous sessions
    const totalMinutesProcessed =
      (userUsageStats[0]?.totalMinutesProcessed || 0) +
      (anonymousStats[0]?.totalMinutesProcessed || 0);

    // Get growth statistics (last 30 days)
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const newUsersLast30Days = await User.countDocuments({
      createdAt: { $gte: thirtyDaysAgo },
    });

    const newAnonymousSessionsLast30Days =
      await AnonymousSession.countDocuments({
        firstUseDate: { $gte: thirtyDaysAgo },
      });

    // Get plan distribution
    const planDistribution = await User.aggregate([
      {
        $group: {
          _id: "$subscription.plan",
          count: { $sum: 1 },
        },
      },
    ]);

    // Get top users by usage
    const topUsersByUsage = await User.find({})
      .sort({ "usage.totalMinutesUsed": -1 })
      .limit(5)
      .select("name email usage.totalMinutesUsed subscription.plan");

    // System health metrics
    const systemHealth = {
      totalSessions: totalUsers + anonymousSessionCount,
      activeUsers: await User.countDocuments({
        updatedAt: { $gte: thirtyDaysAgo },
      }),
      anonymousSessions: anonymousSessionCount,
      registeredUsers: totalUsers,
      conversionRate:
        totalUsers > 0
          ? ((totalUsers / (totalUsers + anonymousSessionCount)) * 100).toFixed(
              2
            )
          : 0,
    };

    return NextResponse.json({
      // Basic stats for dashboard cards
      totalUsers,
      activeSubscriptions,
      totalRevenue,
      totalMinutesProcessed,

      // Detailed analytics
      analytics: {
        users: {
          total: totalUsers,
          banned: bannedUsers,
          verified: verifiedUsers,
          newLast30Days: newUsersLast30Days,
          avgMinutesPerUser: userUsageStats[0]?.avgMinutesPerUser || 0,
        },

        anonymousSessions: {
          total: anonymousSessionCount,
          totalMinutesProcessed: anonymousStats[0]?.totalMinutesProcessed || 0,
          totalFilesProcessed: anonymousStats[0]?.totalFilesProcessed || 0,
          avgMinutesPerSession: anonymousStats[0]?.avgMinutesPerSession || 0,
          newLast30Days: newAnonymousSessionsLast30Days,
        },

        subscriptions: {
          active: activeSubscriptions,
          totalRevenue,
          planDistribution: planDistribution.reduce((acc, item) => {
            acc[item._id] = item.count;
            return acc;
          }, {} as Record<string, number>),
        },

        usage: {
          totalMinutesProcessed,
          registeredUserMinutes: userUsageStats[0]?.totalMinutesProcessed || 0,
          anonymousUserMinutes: anonymousStats[0]?.totalMinutesProcessed || 0,
          topUsers: topUsersByUsage,
        },

        activity: {
          recentActivity,
          systemHealth,
        },
      },

      // Unique identifiers and updates tracking
      tracking: {
        totalUniqueSessions: totalUsers + anonymousSessionCount,
        lastUpdate: new Date().toISOString(),
        dataPoints: {
          registeredUsers: totalUsers,
          anonymousSessions: anonymousSessionCount,
          totalInteractions:
            totalMinutesProcessed > 0
              ? Math.ceil(totalMinutesProcessed / 5)
              : 0, // Estimate interactions
        },
      },
    });
  } catch (error) {
    console.error("Admin stats error:", error);
    return NextResponse.json(
      { error: "Failed to fetch statistics" },
      { status: 500 }
    );
  }
}
