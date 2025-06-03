import { NextRequest, NextResponse } from "next/server";
import connectToDatabase from "@/lib/mongodb";
import AnonymousSession from "@/models/AnonymousSession";

interface DeviceInfo {
  permanent_id: string;
  machine_id: string;
  created_date: string;
  last_used_date: string;
  linked_email?: string;
  device_name: string;
  registered_online?: boolean;
}

export async function POST(request: NextRequest) {
  try {
    const { permanentId, sessionId, deviceInfo, timestamp, action } =
      await request.json();

    if (!permanentId) {
      return NextResponse.json(
        { error: "Missing permanent ID" },
        { status: 400 }
      );
    }

    await connectToDatabase();

    const clientIP =
      request.headers.get("x-forwarded-for") ||
      request.headers.get("x-real-ip") ||
      "unknown";
    const userAgent = request.headers.get("user-agent") || "unknown";

    // Handle check_exists action
    if (action === "check_exists") {
      const existingDevice = await AnonymousSession.findOne({
        sessionId: permanentId,
      });

      return NextResponse.json({
        exists: !!existingDevice,
        deviceId: permanentId,
      });
    }

    // Handle create action
    if (action === "create") {
      const existingDevice = await AnonymousSession.findOne({
        sessionId: permanentId,
      });

      if (existingDevice) {
        return NextResponse.json(
          { error: "Device already exists" },
          { status: 409 }
        );
      }

      // Create new device registration using permanent ID as session ID
      await AnonymousSession.create({
        sessionId: permanentId, // Use permanent ID as session ID for device tracking
        totalMinutesUsed: 0,
        filesProcessed: 0,
        firstUseDate: new Date(deviceInfo?.created_date || new Date()),
        lastUseDate: new Date(),
        ipAddress: clientIP,
        userAgent: userAgent,
        files: [],
        // Store device info
        deviceInfo: {
          permanentId,
          machineId: deviceInfo?.machine_id,
          deviceName: deviceInfo?.device_name,
          linkedEmail: deviceInfo?.linked_email,
          lastSeen: new Date(),
          registeredOnline: true,
        },
      });

      return NextResponse.json({
        success: true,
        message: "Device registered successfully",
        deviceId: permanentId,
        sessionId: permanentId,
        timestamp: new Date().toISOString(),
      });
    }

    // Handle update action
    if (action === "update") {
      await AnonymousSession.findOneAndUpdate(
        { sessionId: permanentId },
        {
          lastUseDate: new Date(),
          ipAddress: clientIP,
          userAgent: userAgent,
          "deviceInfo.lastSeen": new Date(),
          "deviceInfo.linkedEmail": deviceInfo?.linked_email,
          "deviceInfo.registeredOnline": true,
        }
      );

      return NextResponse.json({
        success: true,
        message: "Device updated successfully",
        deviceId: permanentId,
        timestamp: new Date().toISOString(),
      });
    }

    // Default behavior for backward compatibility (when no action specified)
    if (!action) {
      // Check if we already have this device registered
      let existingSession = await AnonymousSession.findOne({
        sessionId: permanentId,
      });

      if (!existingSession) {
        // Create new device registration
        await AnonymousSession.create({
          sessionId: permanentId, // Use permanent ID as session ID for device tracking
          totalMinutesUsed: 0,
          filesProcessed: 0,
          firstUseDate: new Date(deviceInfo?.created_date || new Date()),
          lastUseDate: new Date(),
          ipAddress: clientIP,
          userAgent: userAgent,
          files: [],
          deviceInfo: {
            permanentId,
            machineId: deviceInfo?.machine_id,
            deviceName: deviceInfo?.device_name,
            linkedEmail: deviceInfo?.linked_email,
            lastSeen: new Date(),
            registeredOnline: true,
          },
        });
      } else {
        // Update existing device registration
        await AnonymousSession.findOneAndUpdate(
          { sessionId: permanentId },
          {
            lastUseDate: new Date(),
            ipAddress: clientIP,
            userAgent: userAgent,
            "deviceInfo.lastSeen": new Date(),
            "deviceInfo.linkedEmail":
              deviceInfo?.linked_email ||
              existingSession.deviceInfo?.linkedEmail,
            "deviceInfo.registeredOnline": true,
          }
        );
      }

      return NextResponse.json({
        success: true,
        message: "Device registered successfully",
        deviceId: permanentId,
        sessionId: permanentId,
        timestamp: new Date().toISOString(),
      });
    }

    return NextResponse.json({ error: "Invalid action" }, { status: 400 });
  } catch (error) {
    console.error("Device registration error:", error);
    return NextResponse.json(
      { error: "Failed to register device" },
      { status: 500 }
    );
  }
}
