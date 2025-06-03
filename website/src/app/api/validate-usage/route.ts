import { NextRequest, NextResponse } from "next/server";
import connectToDatabase from "@/lib/mongodb";
import User from "@/models/User";

export async function POST(request: NextRequest) {
  try {
    const { sessionId, fileDuration, userIdentifier } = await request.json();

    if (!sessionId || fileDuration === undefined) {
      return NextResponse.json(
        { error: "Missing required parameters" },
        { status: 400 }
      );
    }

    await connectToDatabase();

    let user = null;

    // If user identifier is provided, try to find the user
    if (userIdentifier) {
      user = await User.findOne({
        $or: [{ email: userIdentifier }, { _id: userIdentifier }],
      });
    }

    // If no user found and no identifier provided, treat as anonymous free user
    if (!user) {
      // For anonymous users, we'll track usage by session
      // For now, allow up to 60 minutes per session for anonymous users
      const currentMonth = new Date().toISOString().slice(0, 7);

      return NextResponse.json({
        allowed: fileDuration <= 60, // Free plan limit
        message:
          fileDuration <= 60
            ? `You can process this ${fileDuration.toFixed(
                1
              )} minute file. Free users get 60 minutes per month.`
            : `This file is ${fileDuration.toFixed(
                1
              )} minutes long. Free users are limited to 60 minutes per month. Please sign up for unlimited processing.`,
        user: null,
        requiresAuth: fileDuration > 60,
        remainingMinutes: Math.max(0, 60 - fileDuration),
        upgradeUrl: "/pricing",
      });
    }

    // Check if user is banned
    if (user.banned) {
      return NextResponse.json({
        allowed: false,
        message: "Your account has been suspended. Please contact support.",
        user: null,
        requiresAuth: false,
        error: true,
      });
    }

    // Check subscription and usage
    const currentMonth = new Date().toISOString().slice(0, 7);
    const currentUsage = user.usage.monthlyUsage.find(
      (usage: any) => usage.month === currentMonth
    );
    const usedMinutes = currentUsage ? currentUsage.minutes : 0;

    let allowed = false;
    let message = "";
    let remainingMinutes = 0;

    if (user.subscription.plan === "free") {
      const totalAfterProcessing = usedMinutes + fileDuration;
      allowed = totalAfterProcessing <= 60;
      remainingMinutes = Math.max(0, 60 - usedMinutes);

      if (allowed) {
        message = `You can process this ${fileDuration.toFixed(
          1
        )} minute file. You have ${remainingMinutes.toFixed(
          1
        )} minutes remaining this month.`;
      } else {
        message = `This file would exceed your monthly limit. You've used ${usedMinutes.toFixed(
          1
        )} minutes out of 60. Upgrade for unlimited processing.`;
      }
    } else {
      // Paid plans have unlimited usage
      allowed = true;
      message = `Processing ${fileDuration.toFixed(
        1
      )} minute file. You have unlimited processing with your ${
        user.subscription.plan
      } plan.`;
      remainingMinutes = -1; // Unlimited
    }

    return NextResponse.json({
      allowed,
      message,
      user: {
        id: user._id.toString(),
        email: user.email,
        name: user.name,
        subscription: user.subscription,
        usage: {
          currentMonth: usedMinutes,
          totalMinutes: user.usage.totalMinutesUsed,
        },
      },
      requiresAuth: false,
      remainingMinutes,
      upgradeUrl: "/pricing",
    });
  } catch (error) {
    console.error("Validate usage error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
