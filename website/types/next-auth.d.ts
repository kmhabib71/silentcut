import NextAuth from "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      email: string;
      name: string;
      image?: string;
      isAdmin: boolean;
      banned: boolean;
      subscription: {
        plan: "free" | "monthly" | "yearly";
        status: "active" | "cancelled" | "expired";
        startDate: string;
        endDate?: string;
      };
    };
  }

  interface User {
    id: string;
    email: string;
    name: string;
    image?: string;
    isAdmin: boolean;
    banned: boolean;
    subscription: {
      plan: "free" | "monthly" | "yearly";
      status: "active" | "cancelled" | "expired";
      startDate: string;
      endDate?: string;
    };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id: string;
    isAdmin: boolean;
    banned: boolean;
    subscription: {
      plan: "free" | "monthly" | "yearly";
      status: "active" | "cancelled" | "expired";
      startDate: string;
      endDate?: string;
    };
  }
}
