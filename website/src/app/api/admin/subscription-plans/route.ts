import { NextRequest, NextResponse } from "next/server";
import connectToDatabase from "@/lib/mongodb";
import User from "@/models/User";

// Define subscription plan limits and pricing
export const SUBSCRIPTION_PLANS = {
  free: {
    name: "Free Plan",
    price: 0,
    monthlyMinutes: 60,
    features: ["60 minutes per month", "Basic support"],
  },
  monthly: {
    name: "Monthly Plan",
    price: 9,
    monthlyMinutes: -1, // -1 indicates unlimited
    features: [
      "Unlimited minutes per month",
      "Priority support",
      "Advanced features",
    ],
  },
  yearly: {
    name: "Yearly Plan",
    price: 59,
    monthlyMinutes: -1, // -1 indicates unlimited
    features: [
      "Unlimited minutes per year",
      "Priority support",
      "Advanced features",
      "20% savings",
    ],
  },
};

export async function GET(request: NextRequest) {
  try {
    await connectToDatabase();

    // Get subscription statistics
    const stats = await User.aggregate([
      {
        $group: {
          _id: "$subscription.plan",
          count: { $sum: 1 },
          totalRevenue: {
            $sum: {
              $cond: {
                if: { $eq: ["$subscription.plan", "monthly"] },
                then: 9,
                else: {
                  $cond: {
                    if: { $eq: ["$subscription.plan", "yearly"] },
                    then: 59,
                    else: 0,
                  },
                },
              },
            },
          },
          avgUsage: { $avg: "$usage.totalMinutesUsed" },
        },
      },
    ]);

    return NextResponse.json({
      success: true,
      plans: SUBSCRIPTION_PLANS,
      statistics: stats,
      totalUsers: await User.countDocuments(),
      activeSubscriptions: await User.countDocuments({
        "subscription.plan": { $ne: "free" },
        "subscription.status": "active",
      }),
    });
  } catch (error) {
    console.error("Get subscription plans error:", error);
    return NextResponse.json(
      { error: "Failed to get subscription data" },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const { action, userId, newPlan, price, adminId } = await request.json();

    await connectToDatabase();

    if (action === "changePlan") {
      return await changeUserPlan(userId, newPlan, price, adminId);
    } else if (action === "cancelSubscription") {
      return await cancelSubscription(userId, adminId);
    } else if (action === "extendSubscription") {
      return await extendSubscription(userId, adminId);
    } else {
      return NextResponse.json({ error: "Invalid action" }, { status: 400 });
    }
  } catch (error) {
    console.error("Subscription management error:", error);
    return NextResponse.json(
      { error: "Failed to manage subscription" },
      { status: 500 }
    );
  }
}

async function changeUserPlan(
  userId: string,
  newPlan: string,
  price?: number,
  adminId?: string
) {
  try {
    if (!SUBSCRIPTION_PLANS[newPlan as keyof typeof SUBSCRIPTION_PLANS]) {
      return NextResponse.json(
        { error: "Invalid subscription plan" },
        { status: 400 }
      );
    }

    const planDetails =
      SUBSCRIPTION_PLANS[newPlan as keyof typeof SUBSCRIPTION_PLANS];
    const actualPrice = price || planDetails.price;

    const updateData: any = {
      "subscription.plan": newPlan,
      "subscription.status": "active",
      "subscription.startDate": new Date(),
      "subscription.price": actualPrice,
    };

    // Set end date for paid plans
    if (newPlan === "monthly") {
      updateData["subscription.endDate"] = new Date(
        Date.now() + 30 * 24 * 60 * 60 * 1000
      ); // 30 days
    } else if (newPlan === "yearly") {
      updateData["subscription.endDate"] = new Date(
        Date.now() + 365 * 24 * 60 * 60 * 1000
      ); // 365 days
    }

    const user = await User.findByIdAndUpdate(userId, updateData, {
      new: true,
    });

    if (!user) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    return NextResponse.json({
      success: true,
      message: `User plan changed to ${planDetails.name}`,
      user: {
        _id: user._id,
        email: user.email,
        subscription: user.subscription,
      },
    });
  } catch (error) {
    console.error("Change plan error:", error);
    return NextResponse.json(
      { error: "Failed to change plan" },
      { status: 500 }
    );
  }
}

async function cancelSubscription(userId: string, adminId?: string) {
  try {
    const user = await User.findByIdAndUpdate(
      userId,
      {
        "subscription.status": "cancelled",
        "subscription.endDate": new Date(), // Immediate cancellation
      },
      { new: true }
    );

    if (!user) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    return NextResponse.json({
      success: true,
      message: "Subscription cancelled successfully",
      user: {
        _id: user._id,
        email: user.email,
        subscription: user.subscription,
      },
    });
  } catch (error) {
    console.error("Cancel subscription error:", error);
    return NextResponse.json(
      { error: "Failed to cancel subscription" },
      { status: 500 }
    );
  }
}

async function extendSubscription(userId: string, adminId?: string) {
  try {
    const user = await User.findById(userId);

    if (!user) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const currentEndDate = user.subscription.endDate || new Date();
    let newEndDate;

    if (user.subscription.plan === "monthly") {
      newEndDate = new Date(
        currentEndDate.getTime() + 30 * 24 * 60 * 60 * 1000
      ); // Add 30 days
    } else if (user.subscription.plan === "yearly") {
      newEndDate = new Date(
        currentEndDate.getTime() + 365 * 24 * 60 * 60 * 1000
      ); // Add 365 days
    } else {
      return NextResponse.json(
        { error: "Cannot extend free plan" },
        { status: 400 }
      );
    }

    const updatedUser = await User.findByIdAndUpdate(
      userId,
      {
        "subscription.endDate": newEndDate,
        "subscription.status": "active",
      },
      { new: true }
    );

    return NextResponse.json({
      success: true,
      message: "Subscription extended successfully",
      user: {
        _id: updatedUser._id,
        email: updatedUser.email,
        subscription: updatedUser.subscription,
      },
    });
  } catch (error) {
    console.error("Extend subscription error:", error);
    return NextResponse.json(
      { error: "Failed to extend subscription" },
      { status: 500 }
    );
  }
}
