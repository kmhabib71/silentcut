import { NextRequest, NextResponse } from "next/server";
import connectToDatabase from "@/lib/mongodb";
import User from "@/models/User";

export async function POST(request: NextRequest) {
  try {
    const { email, secret } = await request.json();

    // Security: Only allow in development or with specific env var
    if (
      process.env.NODE_ENV === "production" &&
      !process.env.ALLOW_ADMIN_SETUP
    ) {
      return NextResponse.json(
        { error: "Admin setup not allowed in production" },
        { status: 403 }
      );
    }

    // Use environment variable for secret, fallback for development
    const SETUP_SECRET =
      process.env.ADMIN_SETUP_SECRET || "temp-admin-setup-123";

    if (secret !== SETUP_SECRET) {
      return NextResponse.json(
        { error: "Invalid secret key" },
        { status: 401 }
      );
    }

    if (!email) {
      return NextResponse.json({ error: "Email is required" }, { status: 400 });
    }

    await connectToDatabase();

    const user = await User.findOne({ email: email.toLowerCase() });

    if (!user) {
      return NextResponse.json(
        { error: "User not found. Please create an account first." },
        { status: 404 }
      );
    }

    if (user.isAdmin) {
      return NextResponse.json(
        { message: "User is already an admin" },
        { status: 200 }
      );
    }

    // Update user to admin
    user.isAdmin = true;
    await user.save();

    return NextResponse.json({
      success: true,
      message: `User ${email} has been granted admin privileges. Please sign out and sign back in.`,
      user: {
        id: user._id.toString(),
        email: user.email,
        name: user.name,
        isAdmin: user.isAdmin,
      },
    });
  } catch (error) {
    console.error("Setup admin error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
