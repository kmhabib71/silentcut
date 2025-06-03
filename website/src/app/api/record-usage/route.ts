import { NextRequest, NextResponse } from "next/server";
import connectToDatabase from "@/lib/mongodb";
import AnonymousSession from "@/models/AnonymousSession";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    console.log("📥 Received payload:", JSON.stringify(body, null, 2));

    const {
      sessionId,
      permanentId,
      fileDuration,
      fileName,
      userId,
      timestamp,
      offlineUsage,
      deviceInfo,
    } = body;

    // Validate required parameters
    if (!sessionId || !fileDuration || !fileName) {
      console.log("❌ Missing required parameters");
      return NextResponse.json(
        { error: "Missing required parameters" },
        { status: 400 }
      );
    }

    console.log("🔗 Connecting to database...");
    await connectToDatabase();
    console.log("✅ Database connected");

    const clientIP =
      request.headers.get("x-forwarded-for") ||
      request.headers.get("x-real-ip") ||
      "unknown";
    const userAgent = request.headers.get("user-agent") || "unknown";

    console.log("👤 Client info:", { clientIP, userAgent });

    // For anonymous users, store in anonymous sessions
    console.log("🔍 Looking for existing session:", sessionId);
    const existingSession = await AnonymousSession.findOne({ sessionId });
    console.log("📋 Existing session found:", !!existingSession);

    // Prepare update data
    const updateData = {
      sessionId,
      $inc: {
        totalMinutesUsed: fileDuration,
        filesProcessed: 1,
      },
      firstUseDate: existingSession?.firstUseDate || new Date(),
      lastUseDate: new Date(),
      ipAddress: clientIP,
      userAgent: userAgent,
      deviceInfo: {
        permanentId: permanentId || sessionId,
        deviceName: deviceInfo?.device_name || "Unknown Device",
        machineId: deviceInfo?.machine_id,
        linkedEmail: deviceInfo?.linked_email || null,
        lastSeen: new Date(),
        registeredOnline: deviceInfo?.registered_online || false,
      },
      $push: {
        files: {
          fileName,
          durationMinutes: fileDuration,
          processedDate: new Date(),
        },
      },
    };

    console.log(
      "💾 Updating session with data:",
      JSON.stringify(updateData, null, 2)
    );

    // Update the current session
    const updatedSession = await AnonymousSession.findOneAndUpdate(
      { sessionId },
      updateData,
      { upsert: true, new: true }
    );

    console.log("✅ Session updated successfully:", updatedSession._id);

    const responseData = {
      success: true,
      message: "Usage recorded for anonymous user",
      sessionStats: {
        sessionId,
        permanentId: permanentId,
        totalMinutesUsed: updatedSession.totalMinutesUsed,
        filesProcessed: updatedSession.filesProcessed,
        remainingFreeMinutes: Math.max(0, 60 - updatedSession.totalMinutesUsed),
      },
      deviceLinked: false,
    };

    console.log("📤 Sending response:", JSON.stringify(responseData, null, 2));

    return NextResponse.json(responseData);
  } catch (error: any) {
    console.error("❌ Record usage error:", error);
    console.error("Error stack:", error.stack);
    return NextResponse.json(
      {
        error: "Internal server error",
        message: error.message,
        stack: process.env.NODE_ENV === "development" ? error.stack : undefined,
      },
      { status: 500 }
    );
  }
}
