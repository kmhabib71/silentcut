import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import connectToDatabase from "@/lib/mongodb";
import User from "@/models/User";

export async function POST(request: NextRequest) {
  try {
    const { email, password, sessionId } = await request.json();

    if (!email || !password || !sessionId) {
      return NextResponse.json(
        { error: "Missing required parameters" },
        { status: 400 }
      );
    }

    await connectToDatabase();

    // Find user by email
    const user = await User.findOne({ email: email.toLowerCase() }).select(
      "+password"
    );

    if (!user || !user.password) {
      return NextResponse.json({
        success: false,
        message: "Invalid email or password",
      });
    }

    // Check password
    const isPasswordValid = await bcrypt.compare(password, user.password);
    if (!isPasswordValid) {
      return NextResponse.json({
        success: false,
        message: "Invalid email or password",
      });
    }

    // Check if user is banned
    if (user.banned) {
      return NextResponse.json({
        success: false,
        message: "Your account has been suspended. Please contact support.",
      });
    }

    // Return user information
    return NextResponse.json({
      success: true,
      message: "Authentication successful",
      user: {
        id: user._id.toString(),
        email: user.email,
        name: user.name,
        avatar: user.avatar,
        subscription: user.subscription,
        usage: {
          currentMonth:
            user.usage.monthlyUsage.find(
              (usage: any) =>
                usage.month === new Date().toISOString().slice(0, 7)
            )?.minutes || 0,
          totalMinutes: user.usage.totalMinutesUsed,
        },
        isAdmin: user.isAdmin,
      },
    });
  } catch (error) {
    console.error("Login error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
