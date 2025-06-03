import { NextRequest, NextResponse } from "next/server";
import connectToDatabase from "@/lib/mongodb";
import User from "@/models/User";
import AnonymousSession from "@/models/AnonymousSession";

export async function POST(request: NextRequest) {
  try {
    const {
      action,
      targetId,
      targetType, // 'user' or 'anonymous'
      reason,
      duration, // in hours, optional
      adminId,
    } = await request.json();

    await connectToDatabase();

    if (action === "block") {
      return await blockUser(targetId, targetType, reason, duration, adminId);
    } else if (action === "unblock") {
      return await unblockUser(targetId, targetType, adminId);
    } else {
      return NextResponse.json({ error: "Invalid action" }, { status: 400 });
    }
  } catch (error) {
    console.error("Block user error:", error);
    return NextResponse.json(
      { error: "Failed to process blocking request" },
      { status: 500 }
    );
  }
}

async function blockUser(
  targetId: string,
  targetType: string,
  reason: string,
  duration?: number,
  adminId?: string
) {
  try {
    const blockData = {
      isBlocked: true,
      blockedAt: new Date(),
      blockedBy: adminId || "admin",
      reason: reason || "Blocked by admin",
      ...(duration && {
        blockedUntil: new Date(Date.now() + duration * 60 * 60 * 1000),
      }), // Convert hours to milliseconds
    };

    let result;
    if (targetType === "user") {
      result = await User.findByIdAndUpdate(
        targetId,
        {
          blocking: blockData,
          banned: true, // Also set banned for backward compatibility
        },
        { new: true }
      );
    } else if (targetType === "anonymous") {
      result = await AnonymousSession.findOneAndUpdate(
        {
          $or: [
            { _id: targetId },
            { sessionId: targetId },
            { "deviceInfo.permanentId": targetId },
          ],
        },
        { blocking: blockData },
        { new: true }
      );
    }

    if (!result) {
      return NextResponse.json(
        { error: "User/Session not found" },
        { status: 404 }
      );
    }

    return NextResponse.json({
      success: true,
      message: `${
        targetType === "user" ? "User" : "Anonymous session"
      } blocked successfully`,
      blocked: true,
      blockedUntil: blockData.blockedUntil,
      reason: blockData.reason,
    });
  } catch (error) {
    console.error("Block operation error:", error);
    return NextResponse.json(
      { error: "Failed to block user" },
      { status: 500 }
    );
  }
}

async function unblockUser(
  targetId: string,
  targetType: string,
  adminId?: string
) {
  try {
    const unblockData = {
      isBlocked: false,
      blockedAt: undefined,
      blockedBy: undefined,
      reason: undefined,
      blockedUntil: undefined,
    };

    let result;
    if (targetType === "user") {
      result = await User.findByIdAndUpdate(
        targetId,
        {
          blocking: unblockData,
          banned: false, // Also unset banned for backward compatibility
        },
        { new: true }
      );
    } else if (targetType === "anonymous") {
      result = await AnonymousSession.findOneAndUpdate(
        {
          $or: [
            { _id: targetId },
            { sessionId: targetId },
            { "deviceInfo.permanentId": targetId },
          ],
        },
        { blocking: unblockData },
        { new: true }
      );
    }

    if (!result) {
      return NextResponse.json(
        { error: "User/Session not found" },
        { status: 404 }
      );
    }

    return NextResponse.json({
      success: true,
      message: `${
        targetType === "user" ? "User" : "Anonymous session"
      } unblocked successfully`,
      blocked: false,
    });
  } catch (error) {
    console.error("Unblock operation error:", error);
    return NextResponse.json(
      { error: "Failed to unblock user" },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  try {
    await connectToDatabase();

    // Get all blocked users and sessions
    const blockedUsers = await User.find({
      $or: [{ "blocking.isBlocked": true }, { banned: true }],
    }).select("email name blocking banned createdAt");

    const blockedSessions = await AnonymousSession.find({
      "blocking.isBlocked": true,
    }).select("sessionId deviceInfo blocking totalMinutesUsed lastUseDate");

    return NextResponse.json({
      success: true,
      blockedUsers: blockedUsers.map((user) => ({
        _id: user._id,
        email: user.email,
        name: user.name,
        isBlocked: user.blocking?.isBlocked || user.banned,
        blockedAt: user.blocking?.blockedAt,
        blockedBy: user.blocking?.blockedBy,
        reason: user.blocking?.reason,
        blockedUntil: user.blocking?.blockedUntil,
        createdAt: user.createdAt,
      })),
      blockedSessions: blockedSessions.map((session) => ({
        _id: session._id,
        sessionId: session.sessionId,
        permanentId: session.deviceInfo?.permanentId,
        deviceName: session.deviceInfo?.deviceName,
        isBlocked: session.blocking?.isBlocked,
        blockedAt: session.blocking?.blockedAt,
        blockedBy: session.blocking?.blockedBy,
        reason: session.blocking?.reason,
        blockedUntil: session.blocking?.blockedUntil,
        totalMinutesUsed: session.totalMinutesUsed,
        lastUseDate: session.lastUseDate,
      })),
    });
  } catch (error) {
    console.error("Get blocked users error:", error);
    return NextResponse.json(
      { error: "Failed to get blocked users" },
      { status: 500 }
    );
  }
}
