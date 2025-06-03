import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import connectToDatabase from "@/lib/mongodb";
import User from "@/models/User";
import AnonymousSession from "@/models/AnonymousSession";

export async function POST(request: NextRequest) {
  try {
    const { name, email, password, deviceId, sessionId } = await request.json();

    // Validation
    if (!name || !email || !password) {
      return NextResponse.json(
        { message: "Name, email, and password are required" },
        { status: 400 }
      );
    }

    if (password.length < 6) {
      return NextResponse.json(
        { message: "Password must be at least 6 characters long" },
        { status: 400 }
      );
    }

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return NextResponse.json(
        { message: "Please provide a valid email address" },
        { status: 400 }
      );
    }

    await connectToDatabase();

    // Check if user already exists
    const existingUser = await User.findOne({ email: email.toLowerCase() });
    if (existingUser) {
      return NextResponse.json(
        { message: "An account with this email already exists" },
        { status: 409 }
      );
    }

    // Hash password
    const saltRounds = 12;
    const hashedPassword = await bcrypt.hash(password, saltRounds);

    // Create new user
    const newUser = new User({
      name: name.trim(),
      email: email.toLowerCase(),
      password: hashedPassword,
      emailVerified: false, // Email verification can be added later
      subscription: {
        plan: "free",
        status: "active",
        monthlyUsage: 0,
        monthlyLimit: 60, // 60 minutes per month for free plan
        resetDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days from now
      },
      createdAt: new Date(),
    });

    await newUser.save();

    // Link anonymous usage to the new user account if device info provided
    if (deviceId || sessionId) {
      try {
        // Find anonymous sessions associated with this device
        const anonymousSessionsToLink = await AnonymousSession.find({
          $or: [
            { sessionId: deviceId }, // Device-based session
            { sessionId: sessionId }, // Specific session
            { "deviceInfo.permanentId": deviceId }, // Device info match
          ],
        });

        if (anonymousSessionsToLink.length > 0) {
          // Update anonymous sessions to link them to the new user
          await AnonymousSession.updateMany(
            {
              $or: [
                { sessionId: deviceId },
                { sessionId: sessionId },
                { "deviceInfo.permanentId": deviceId },
              ],
            },
            {
              $set: {
                syncedToUser: newUser._id.toString(),
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
            await User.findByIdAndUpdate(newUser._id, {
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
            )} minutes) to new user: ${email}`
          );
        }
      } catch (linkError) {
        console.error("Error linking anonymous usage:", linkError);
        // Don't fail the signup if linking fails
      }
    }

    // Return success (don't include sensitive data)
    return NextResponse.json(
      {
        message: "Account created successfully",
        user: {
          id: newUser._id.toString(),
          name: newUser.name,
          email: newUser.email,
        },
        linkedAnonymousUsage: !!(deviceId || sessionId),
      },
      { status: 201 }
    );
  } catch (error) {
    console.error("Signup error:", error);
    return NextResponse.json(
      { message: "Internal server error. Please try again later." },
      { status: 500 }
    );
  }
}
