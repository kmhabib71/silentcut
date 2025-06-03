import { NextRequest, NextResponse } from "next/server";
import connectToDatabase from "@/lib/mongodb";
import User from "@/models/User";

export async function POST(request: NextRequest) {
  try {
    const { sessionId, fileDuration, fileName, userId, timestamp } =
      await request.json();

    if (!sessionId || !fileDuration || !fileName) {
      return NextResponse.json(
        { error: "Missing required parameters" },
        { status: 400 }
      );
    }

    await connectToDatabase();

    // If userId is provided, record usage for the user
    if (userId) {
      const user = await User.findById(userId);
      if (user && !user.banned) {
        await user.addUsage(fileDuration);

        return NextResponse.json({
          success: true,
          message: "Usage recorded successfully",
          totalUsage: user.usage.totalMinutesUsed,
        });
      }
    }

    // For anonymous users, we'll just return success
    // In a production environment, you might want to track anonymous usage differently
    return NextResponse.json({
      success: true,
      message: "Usage recorded for anonymous user",
    });
  } catch (error) {
    console.error("Record usage error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
