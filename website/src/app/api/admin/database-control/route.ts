import { NextRequest, NextResponse } from "next/server";
import connectToDatabase from "@/lib/mongodb";
import AnonymousSession from "@/models/AnonymousSession";
import User from "@/models/User";

export async function POST(request: NextRequest) {
  try {
    const { action, sessionId, permanentId, newUsage, userEmail } =
      await request.json();

    await connectToDatabase();

    switch (action) {
      case "setUsage":
        return await setUsage(sessionId, permanentId, newUsage);
      case "resetUsage":
        return await resetUsage(sessionId, permanentId);
      case "addTestUsage":
        return await addTestUsage(sessionId, permanentId, newUsage);
      default:
        return NextResponse.json({ error: "Invalid action" }, { status: 400 });
    }
  } catch (error) {
    console.error("Database control error:", error);
    return NextResponse.json(
      { error: "Failed to control database" },
      { status: 500 }
    );
  }
}

async function setUsage(
  sessionId: string,
  permanentId: string,
  newUsage: number
) {
  try {
    // Update anonymous session
    const result = await AnonymousSession.findOneAndUpdate(
      {
        $or: [
          { sessionId: sessionId },
          { "deviceInfo.permanentId": permanentId },
        ],
      },
      {
        totalMinutesUsed: newUsage,
        lastUseDate: new Date(),
        $push: {
          files: {
            fileName: `admin_test_${newUsage}min.mp4`,
            durationMinutes: newUsage,
            processedDate: new Date(),
          },
        },
      },
      { upsert: true, new: true }
    );

    return NextResponse.json({
      success: true,
      message: `Usage set to ${newUsage} minutes`,
      sessionId: result.sessionId,
      totalMinutesUsed: result.totalMinutesUsed,
    });
  } catch (error) {
    console.error("Set usage error:", error);
    return NextResponse.json({ error: "Failed to set usage" }, { status: 500 });
  }
}

async function resetUsage(sessionId: string, permanentId: string) {
  try {
    const result = await AnonymousSession.findOneAndUpdate(
      {
        $or: [
          { sessionId: sessionId },
          { "deviceInfo.permanentId": permanentId },
        ],
      },
      {
        totalMinutesUsed: 0,
        filesProcessed: 0,
        files: [],
        lastUseDate: new Date(),
      },
      { new: true }
    );

    return NextResponse.json({
      success: true,
      message: "Usage reset to 0 minutes",
      sessionId: result?.sessionId,
      totalMinutesUsed: 0,
    });
  } catch (error) {
    console.error("Reset usage error:", error);
    return NextResponse.json(
      { error: "Failed to reset usage" },
      { status: 500 }
    );
  }
}

async function addTestUsage(
  sessionId: string,
  permanentId: string,
  additionalMinutes: number
) {
  try {
    const session = await AnonymousSession.findOne({
      $or: [
        { sessionId: sessionId },
        { "deviceInfo.permanentId": permanentId },
      ],
    });

    const currentUsage = session?.totalMinutesUsed || 0;
    const newTotal = currentUsage + additionalMinutes;

    const result = await AnonymousSession.findOneAndUpdate(
      {
        $or: [
          { sessionId: sessionId },
          { "deviceInfo.permanentId": permanentId },
        ],
      },
      {
        totalMinutesUsed: newTotal,
        lastUseDate: new Date(),
        $push: {
          files: {
            fileName: `admin_add_${additionalMinutes}min.mp4`,
            durationMinutes: additionalMinutes,
            processedDate: new Date(),
          },
        },
      },
      { upsert: true, new: true }
    );

    return NextResponse.json({
      success: true,
      message: `Added ${additionalMinutes} minutes (total: ${newTotal})`,
      sessionId: result.sessionId,
      totalMinutesUsed: result.totalMinutesUsed,
    });
  } catch (error) {
    console.error("Add test usage error:", error);
    return NextResponse.json({ error: "Failed to add usage" }, { status: 500 });
  }
}

export async function GET(request: NextRequest) {
  try {
    await connectToDatabase();

    // Get all sessions for admin management
    const sessions = await AnonymousSession.find({}).sort({ lastUseDate: -1 });
    const users = await User.find({}).sort({ createdAt: -1 });

    return NextResponse.json({
      success: true,
      anonymousSessions: sessions.map((session) => ({
        sessionId: session.sessionId,
        permanentId: session.deviceInfo?.permanentId,
        totalMinutesUsed: session.totalMinutesUsed,
        filesProcessed: session.filesProcessed,
        lastUseDate: session.lastUseDate,
        deviceName: session.deviceInfo?.deviceName,
        files: session.files,
      })),
      users: users.map((user) => ({
        _id: user._id,
        email: user.email,
        totalMinutesUsed: user.totalMinutesUsed,
        filesProcessed: user.filesProcessed,
        subscriptionType: user.subscriptionType,
        lastLogin: user.lastLogin,
      })),
    });
  } catch (error) {
    console.error("Get database data error:", error);
    return NextResponse.json(
      { error: "Failed to get database data" },
      { status: 500 }
    );
  }
}
