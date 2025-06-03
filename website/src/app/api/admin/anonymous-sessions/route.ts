import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import connectToDatabase from "@/lib/mongodb";
import AnonymousSession from "@/models/AnonymousSession";

export async function GET(request: NextRequest) {
  try {
    // Check if user is admin
    const session = await getServerSession(authOptions);
    if (!session?.user?.isAdmin) {
      return NextResponse.json(
        { error: "Admin access required" },
        { status: 403 }
      );
    }

    await connectToDatabase();

    // Get URL parameters for pagination and search
    const { searchParams } = new URL(request.url);
    const page = parseInt(searchParams.get("page") || "1");
    const limit = parseInt(searchParams.get("limit") || "20");
    const search = searchParams.get("search") || "";
    const sortBy = searchParams.get("sortBy") || "lastUseDate";
    const sortOrder = searchParams.get("sortOrder") || "desc";

    // Build search query
    const searchQuery: any = {};
    if (search) {
      searchQuery.$or = [
        { sessionId: { $regex: search, $options: "i" } },
        { ipAddress: { $regex: search, $options: "i" } },
        { "deviceInfo.deviceName": { $regex: search, $options: "i" } },
        { "deviceInfo.linkedEmail": { $regex: search, $options: "i" } },
      ];
    }

    // Calculate skip for pagination
    const skip = (page - 1) * limit;

    // Build sort object
    const sort: any = {};
    sort[sortBy] = sortOrder === "desc" ? -1 : 1;

    // Fetch anonymous sessions with pagination
    const anonymousSessions = await AnonymousSession.find(searchQuery)
      .sort(sort)
      .skip(skip)
      .limit(limit)
      .lean();

    // Get total count for pagination
    const totalCount = await AnonymousSession.countDocuments(searchQuery);
    const totalPages = Math.ceil(totalCount / limit);

    // Format the data for display
    const formattedSessions = anonymousSessions.map((session) => ({
      id: session._id,
      sessionId: session.sessionId,
      permanentId: session.deviceInfo?.permanentId || session.sessionId,
      deviceName: session.deviceInfo?.deviceName || "Unknown Device",
      linkedEmail: session.deviceInfo?.linkedEmail || null,
      totalMinutesUsed: session.totalMinutesUsed,
      filesProcessed: session.filesProcessed,
      firstUseDate: session.firstUseDate,
      lastUseDate: session.lastUseDate,
      ipAddress: session.ipAddress,
      userAgent: session.userAgent,
      registeredOnline: session.deviceInfo?.registeredOnline || false,
      syncedToUser: session.syncedToUser,
      files: session.files,
      createdAt: session.createdAt,
      updatedAt: session.updatedAt,
    }));

    return NextResponse.json({
      sessions: formattedSessions,
      pagination: {
        currentPage: page,
        totalPages,
        totalCount,
        hasNext: page < totalPages,
        hasPrev: page > 1,
      },
      summary: {
        totalSessions: totalCount,
        registeredOnline: anonymousSessions.filter(
          (s) => s.deviceInfo?.registeredOnline
        ).length,
        withLinkedEmail: anonymousSessions.filter(
          (s) => s.deviceInfo?.linkedEmail
        ).length,
        totalMinutesProcessed: anonymousSessions.reduce(
          (sum, s) => sum + (s.totalMinutesUsed || 0),
          0
        ),
        totalFilesProcessed: anonymousSessions.reduce(
          (sum, s) => sum + (s.filesProcessed || 0),
          0
        ),
      },
    });
  } catch (error) {
    console.error("Anonymous sessions fetch error:", error);
    return NextResponse.json(
      { error: "Failed to fetch anonymous sessions" },
      { status: 500 }
    );
  }
}
