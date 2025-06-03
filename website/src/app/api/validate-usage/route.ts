import { NextRequest, NextResponse } from "next/server";
import connectToDatabase from "@/lib/mongodb";
import User from "@/models/User";
import AnonymousSession from "@/models/AnonymousSession";

export async function POST(request: NextRequest) {
  try {
    const {
      sessionId,
      permanentId,
      fileDuration,
      userIdentifier,
      offlineUsage,
      deviceInfo,
    } = await request.json();

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

      // If user found and we have a permanent ID, link them
      if (user && permanentId) {
        // Update the permanent device record with user info
        await AnonymousSession.findOneAndUpdate(
          { sessionId: permanentId },
          {
            syncedToUser: user._id,
            "deviceInfo.linkedEmail": user.email,
          }
        );
      }
    }

    // Handle authenticated users
    if (user) {
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
        permanentId: permanentId,
        deviceLinked: true,
      });
    }

    // Handle anonymous users (with or without offline usage data)
    let anonymousUsage = 0;

    // First check if we have offline usage data from the client
    if (offlineUsage && offlineUsage.total_minutes_used) {
      anonymousUsage = offlineUsage.total_minutes_used;
    } else if (permanentId) {
      // Check if we have this permanent device in our database
      const existingDevice = await AnonymousSession.findOne({
        sessionId: permanentId,
      });
      if (existingDevice) {
        anonymousUsage = existingDevice.totalMinutesUsed;
      }
    } else {
      // Check if we have this session in our database
      const existingSession = await AnonymousSession.findOne({ sessionId });
      if (existingSession) {
        anonymousUsage = existingSession.totalMinutesUsed;
      }
    }

    const freeLimit = 60; // 60 minutes for anonymous users
    const totalAfterProcessing = anonymousUsage + fileDuration;
    const canProcess = totalAfterProcessing <= freeLimit;
    const remainingMinutes = Math.max(0, freeLimit - anonymousUsage);

    return NextResponse.json({
      allowed: canProcess,
      message: canProcess
        ? `You can process this ${fileDuration.toFixed(
            1
          )} minute file. ${remainingMinutes.toFixed(
            1
          )} minutes remaining in your free quota.`
        : `This ${fileDuration.toFixed(
            1
          )} minute file would exceed your free limit by ${(
            totalAfterProcessing - freeLimit
          ).toFixed(1)} minutes. Sign up for unlimited processing.`,
      user: null,
      requiresAuth: !canProcess,
      remainingMinutes: remainingMinutes,
      upgradeUrl: !canProcess ? "/pricing" : null,
      anonymousUsage: {
        current: anonymousUsage,
        afterProcessing: totalAfterProcessing,
        limit: freeLimit,
        sessionId: sessionId,
      },
      permanentId: permanentId,
      deviceLinked: false,
    });
  } catch (error) {
    console.error("Validate usage error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
