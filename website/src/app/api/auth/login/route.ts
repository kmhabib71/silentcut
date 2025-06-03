import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import connectToDatabase from "@/lib/mongodb";
import User from "@/models/User";
import AnonymousSession from "@/models/AnonymousSession";

export async function POST(request: NextRequest) {
  try {
    const { email, password, sessionId, deviceId, permanentId } =
      await request.json();

    if (!email || !password) {
      return NextResponse.json(
        { error: "Email and password are required" },
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

    // Link anonymous usage to the user account if device info provided
    if (deviceId || sessionId || permanentId) {
      try {
        const deviceIdentifier = deviceId || permanentId;

        // Find anonymous sessions associated with this device
        const anonymousSessionsToLink = await AnonymousSession.find({
          $or: [
            { sessionId: deviceIdentifier }, // Device-based session
            { sessionId: sessionId }, // Specific session
            { "deviceInfo.permanentId": deviceIdentifier }, // Device info match
          ],
          syncedToUser: { $exists: false }, // Only link sessions not already linked
        });

        if (anonymousSessionsToLink.length > 0) {
          // Update anonymous sessions to link them to the user
          await AnonymousSession.updateMany(
            {
              $or: [
                { sessionId: deviceIdentifier },
                { sessionId: sessionId },
                { "deviceInfo.permanentId": deviceIdentifier },
              ],
              syncedToUser: { $exists: false },
            },
            {
              $set: {
                syncedToUser: user._id.toString(),
                "deviceInfo.linkedEmail": email.toLowerCase(),
              },
            }
          );

          // Calculate total anonymous usage to add to user's usage
          const totalAnonymousMinutes = anonymousSessionsToLink.reduce(
            (sum, session) => sum + (session.totalMinutesUsed || 0),
            0
          );

          // Update user's usage with anonymous usage
          if (totalAnonymousMinutes > 0) {
            await User.findByIdAndUpdate(user._id, {
              $inc: {
                "usage.totalMinutesUsed": totalAnonymousMinutes,
              },
            });
          }

          console.log(
            `✅ Linked ${
              anonymousSessionsToLink.length
            } anonymous sessions (${totalAnonymousMinutes.toFixed(
              1
            )} minutes) to existing user: ${email}`
          );
        }
      } catch (linkError) {
        console.error("Error linking anonymous usage during login:", linkError);
        // Don't fail the login if linking fails
      }
    }

    // Get updated user data after potential usage linking
    const updatedUser = await User.findById(user._id);

    // Return user information
    return NextResponse.json({
      success: true,
      message: "Authentication successful",
      user: {
        id: updatedUser._id.toString(),
        email: updatedUser.email,
        name: updatedUser.name,
        avatar: updatedUser.avatar,
        subscription: updatedUser.subscription,
        usage: {
          currentMonth:
            updatedUser.usage.monthlyUsage.find(
              (usage: any) =>
                usage.month === new Date().toISOString().slice(0, 7)
            )?.minutes || 0,
          totalMinutes: updatedUser.usage.totalMinutesUsed,
        },
        isAdmin: updatedUser.isAdmin,
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
