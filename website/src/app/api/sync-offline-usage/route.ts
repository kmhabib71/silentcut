import { NextRequest, NextResponse } from "next/server";
import connectToDatabase from "@/lib/mongodb";
import User from "@/models/User";
import AnonymousSession from "@/models/AnonymousSession";

interface OfflineSession {
  session_id: string;
  permanent_id?: string;
  total_minutes_used: number;
  files_processed: number;
  first_use_date: string;
  last_use_date: string;
  user_email?: string;
}

export async function POST(request: NextRequest) {
  try {
    const { sessionId, permanentId, offlineSessions, deviceInfo } =
      await request.json();

    if (!sessionId || !offlineSessions) {
      return NextResponse.json(
        { error: "Missing required parameters" },
        { status: 400 }
      );
    }

    await connectToDatabase();

    const syncResults = [];
    const clientIP =
      request.headers.get("x-forwarded-for") ||
      request.headers.get("x-real-ip") ||
      "unknown";
    const userAgent = request.headers.get("user-agent") || "unknown";

    // Update permanent device record if available
    if (permanentId && deviceInfo) {
      await AnonymousSession.findOneAndUpdate(
        { sessionId: permanentId },
        {
          lastUseDate: new Date(),
          ipAddress: clientIP,
          userAgent: userAgent,
          "deviceInfo.lastSeen": new Date(),
          "deviceInfo.linkedEmail": deviceInfo.linked_email,
        }
      );
    }

    for (const session of offlineSessions as OfflineSession[]) {
      try {
        // If there's a user email, try to associate with user account
        if (session.user_email) {
          const user = await User.findOne({
            email: session.user_email.toLowerCase(),
          });

          if (user) {
            const currentMonth = new Date().toISOString().slice(0, 7);

            // Update user's usage
            const existingUsageIndex = user.usage.monthlyUsage.findIndex(
              (usage: any) => usage.month === currentMonth
            );

            if (existingUsageIndex >= 0) {
              user.usage.monthlyUsage[existingUsageIndex].minutes +=
                session.total_minutes_used;
            } else {
              user.usage.monthlyUsage.push({
                month: currentMonth,
                minutes: session.total_minutes_used,
              });
            }

            user.usage.totalMinutesUsed += session.total_minutes_used;
            await user.save();

            // Also store in anonymous sessions but mark as synced to user
            await AnonymousSession.findOneAndUpdate(
              { sessionId: session.session_id },
              {
                sessionId: session.session_id,
                totalMinutesUsed: session.total_minutes_used,
                filesProcessed: session.files_processed,
                firstUseDate: new Date(session.first_use_date),
                lastUseDate: new Date(session.last_use_date),
                ipAddress: clientIP,
                userAgent: userAgent,
                syncedToUser: user._id,
                permanentDeviceId: session.permanent_id || permanentId,
              },
              { upsert: true, new: true }
            );

            // Update permanent device record with user linkage
            if (session.permanent_id || permanentId) {
              await AnonymousSession.findOneAndUpdate(
                { sessionId: session.permanent_id || permanentId },
                {
                  syncedToUser: user._id,
                  "deviceInfo.linkedEmail": user.email,
                  lastUseDate: new Date(),
                }
              );
            }

            syncResults.push({
              session_id: session.session_id,
              status: "synced_to_user",
              user_id: user._id.toString(),
              minutes_synced: session.total_minutes_used,
              permanent_id: session.permanent_id || permanentId,
            });
          } else {
            // Store as anonymous session if user not found
            await AnonymousSession.findOneAndUpdate(
              { sessionId: session.session_id },
              {
                sessionId: session.session_id,
                totalMinutesUsed: session.total_minutes_used,
                filesProcessed: session.files_processed,
                firstUseDate: new Date(session.first_use_date),
                lastUseDate: new Date(session.last_use_date),
                ipAddress: clientIP,
                userAgent: userAgent,
                permanentDeviceId: session.permanent_id || permanentId,
              },
              { upsert: true, new: true }
            );

            syncResults.push({
              session_id: session.session_id,
              status: "user_not_found",
              stored_as_anonymous: true,
              permanent_id: session.permanent_id || permanentId,
            });
          }
        } else {
          // Store anonymous session data for admin tracking
          await AnonymousSession.findOneAndUpdate(
            { sessionId: session.session_id },
            {
              sessionId: session.session_id,
              totalMinutesUsed: session.total_minutes_used,
              filesProcessed: session.files_processed,
              firstUseDate: new Date(session.first_use_date),
              lastUseDate: new Date(session.last_use_date),
              ipAddress: clientIP,
              userAgent: userAgent,
              permanentDeviceId: session.permanent_id || permanentId,
            },
            { upsert: true, new: true }
          );

          syncResults.push({
            session_id: session.session_id,
            status: "anonymous_session",
            minutes_used: session.total_minutes_used,
            files_processed: session.files_processed,
            permanent_id: session.permanent_id || permanentId,
          });
        }
      } catch (error) {
        console.error(`Failed to sync session ${session.session_id}:`, error);
        syncResults.push({
          session_id: session.session_id,
          status: "error",
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    return NextResponse.json({
      success: true,
      message: `Synced ${offlineSessions.length} offline sessions`,
      results: syncResults,
      permanentId: permanentId,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error("Sync offline usage error:", error);
    return NextResponse.json(
      { error: "Failed to sync offline usage" },
      { status: 500 }
    );
  }
}
