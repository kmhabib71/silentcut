"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  CheckCircle,
  X,
  Zap,
  Crown,
  Star,
  Clock,
  Users,
  Shield,
  Headphones,
  Settings,
  Rocket,
} from "lucide-react";

export default function PricingPage() {
  const [billingCycle, setBillingCycle] = useState<"monthly" | "yearly">(
    "monthly"
  );

  const plans = [
    {
      name: "Free",
      description: "Perfect for trying out our service",
      price: { monthly: 0, yearly: 0 },
      originalPrice: null,
      features: [
        { name: "60 minutes per month", included: true },
        { name: "Basic silence detection", included: true },
        { name: "Standard processing speed", included: true },
        { name: "Email support", included: true },
        { name: "Batch processing", included: false },
        { name: "Priority processing", included: false },
        { name: "Custom presets", included: false },
        { name: "API access", included: false },
        { name: "Premium support", included: false },
      ],
      buttonText: "Get Started Free",
      buttonVariant: "outline" as const,
      popular: false,
      icon: <Zap className="w-6 h-6" />,
    },
    {
      name: "Monthly",
      description: "Great for regular content creators",
      price: { monthly: 9, yearly: 9 },
      originalPrice: null,
      features: [
        { name: "Unlimited processing", included: true },
        { name: "Advanced AI detection", included: true },
        { name: "Priority processing", included: true },
        { name: "Batch processing", included: true },
        { name: "Custom presets", included: true },
        { name: "Premium support", included: true },
        { name: "API access", included: true },
        { name: "Early access to features", included: false },
        { name: "Custom integrations", included: false },
      ],
      buttonText: "Start Monthly Plan",
      buttonVariant: "default" as const,
      popular: true,
      icon: <Crown className="w-6 h-6" />,
    },
    {
      name: "Yearly",
      description: "Best value for professionals",
      price: { monthly: 4.92, yearly: 59 },
      originalPrice: { monthly: 9, yearly: 108 },
      features: [
        { name: "Everything in Monthly", included: true },
        { name: "Save $49 per year", included: true },
        { name: "Priority support", included: true },
        { name: "Early access to features", included: true },
        { name: "Custom integrations", included: true },
        { name: "Dedicated account manager", included: true },
        { name: "Custom training", included: true },
        { name: "SLA guarantee", included: true },
        { name: "White-label options", included: true },
      ],
      buttonText: "Start Yearly Plan",
      buttonVariant: "default" as const,
      popular: false,
      icon: <Star className="w-6 h-6" />,
    },
  ];

  const features = [
    {
      category: "Processing",
      items: [
        {
          name: "Monthly processing limit",
          free: "60 minutes",
          monthly: "Unlimited",
          yearly: "Unlimited",
        },
        {
          name: "Processing speed",
          free: "Standard",
          monthly: "Priority",
          yearly: "Priority",
        },
        { name: "Batch processing", free: "✗", monthly: "✓", yearly: "✓" },
        { name: "Custom presets", free: "✗", monthly: "✓", yearly: "✓" },
        { name: "API access", free: "✗", monthly: "✓", yearly: "✓" },
      ],
    },
    {
      category: "Support",
      items: [
        { name: "Email support", free: "✓", monthly: "✓", yearly: "✓" },
        { name: "Priority support", free: "✗", monthly: "✓", yearly: "✓" },
        { name: "Phone support", free: "✗", monthly: "✗", yearly: "✓" },
        {
          name: "Dedicated account manager",
          free: "✗",
          monthly: "✗",
          yearly: "✓",
        },
      ],
    },
    {
      category: "Features",
      items: [
        {
          name: "Early access to features",
          free: "✗",
          monthly: "✗",
          yearly: "✓",
        },
        { name: "Custom integrations", free: "✗", monthly: "✗", yearly: "✓" },
        { name: "White-label options", free: "✗", monthly: "✗", yearly: "✓" },
        { name: "SLA guarantee", free: "✗", monthly: "✗", yearly: "✓" },
      ],
    },
  ];

  const handleSubscribe = async (planName: string) => {
    if (planName === "Free") {
      window.location.href = "/auth/signup";
      return;
    }

    // 2Checkout integration would go here
    // For now, redirect to a payment processing page
    const plan = planName.toLowerCase();
    const cycle = billingCycle;
    window.location.href = `/payment?plan=${plan}&cycle=${cycle}`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Navigation */}
      <nav className="fixed top-0 w-full bg-black/20 backdrop-blur-md z-50 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <Link href="/" className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
                <Zap className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-white">
                SilenceCutter
              </span>
            </Link>

            <div className="flex items-center space-x-4">
              <Link
                href="/auth/signin"
                className="text-gray-300 hover:text-white transition-colors"
              >
                Sign In
              </Link>
              <Link
                href="/auth/signup"
                className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-4 py-2 rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all"
              >
                Get Started
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Header */}
      <section className="pt-32 pb-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-4xl md:text-6xl font-bold text-white mb-6"
          >
            Choose Your Plan
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="text-xl text-gray-300 mb-8"
          >
            Start free and upgrade as your content creation needs grow
          </motion.p>

          {/* Billing Toggle */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="flex items-center justify-center space-x-4 mb-12"
          >
            <span
              className={`text-sm ${
                billingCycle === "monthly" ? "text-white" : "text-gray-400"
              }`}
            >
              Monthly
            </span>
            <button
              onClick={() =>
                setBillingCycle(
                  billingCycle === "monthly" ? "yearly" : "monthly"
                )
              }
              className="relative inline-flex h-6 w-11 items-center rounded-full bg-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2"
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  billingCycle === "yearly" ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
            <span
              className={`text-sm ${
                billingCycle === "yearly" ? "text-white" : "text-gray-400"
              }`}
            >
              Yearly
              <span className="ml-1 text-green-400 text-xs font-medium">
                Save 45%
              </span>
            </span>
          </motion.div>
        </div>
      </section>

      {/* Pricing Cards */}
      <section className="pb-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {plans.map((plan, index) => (
              <motion.div
                key={plan.name}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: index * 0.2 }}
                className={`relative bg-white/5 backdrop-blur-sm border rounded-xl p-8 ${
                  plan.popular
                    ? "border-purple-500 ring-2 ring-purple-500/20 scale-105"
                    : "border-white/10"
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                    <span className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-4 py-1 rounded-full text-sm font-semibold">
                      Most Popular
                    </span>
                  </div>
                )}

                <div className="text-center mb-8">
                  <div className="flex items-center justify-center mb-4">
                    <div className="text-purple-400">{plan.icon}</div>
                  </div>
                  <h3 className="text-2xl font-bold text-white mb-2">
                    {plan.name}
                  </h3>
                  <p className="text-gray-300 mb-4">{plan.description}</p>

                  <div className="mb-2">
                    <span className="text-4xl font-bold text-white">
                      $
                      {billingCycle === "monthly"
                        ? plan.price.monthly
                        : plan.price.yearly}
                    </span>
                    <span className="text-gray-400">
                      /{billingCycle === "yearly" ? "year" : "month"}
                    </span>
                  </div>

                  {plan.originalPrice && billingCycle === "yearly" && (
                    <div className="text-sm text-gray-400">
                      <span className="line-through">
                        ${plan.originalPrice.yearly}/year
                      </span>
                      <span className="ml-2 text-green-400 font-medium">
                        Save $49
                      </span>
                    </div>
                  )}
                </div>

                <ul className="space-y-3 mb-8">
                  {plan.features.map((feature, featureIndex) => (
                    <li
                      key={featureIndex}
                      className="flex items-center space-x-3"
                    >
                      {feature.included ? (
                        <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
                      ) : (
                        <X className="w-5 h-5 text-gray-500 flex-shrink-0" />
                      )}
                      <span
                        className={`text-sm ${
                          feature.included ? "text-gray-300" : "text-gray-500"
                        }`}
                      >
                        {feature.name}
                      </span>
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => handleSubscribe(plan.name)}
                  className={`w-full py-3 px-4 rounded-lg font-semibold transition-all ${
                    plan.buttonVariant === "default"
                      ? "bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600"
                      : "border border-white/20 text-white hover:bg-white/10"
                  }`}
                >
                  {plan.buttonText}
                </button>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature Comparison */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-black/20">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Compare All Features
            </h2>
            <p className="text-xl text-gray-300">
              See exactly what's included in each plan
            </p>
          </div>

          <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl overflow-hidden">
            {features.map((category, categoryIndex) => (
              <div key={category.category}>
                <div className="bg-white/5 px-6 py-4 border-b border-white/10">
                  <h3 className="text-lg font-semibold text-white">
                    {category.category}
                  </h3>
                </div>
                {category.items.map((item, itemIndex) => (
                  <div
                    key={itemIndex}
                    className="grid grid-cols-4 gap-4 px-6 py-4 border-b border-white/5 last:border-b-0"
                  >
                    <div className="text-gray-300">{item.name}</div>
                    <div className="text-center text-gray-300">{item.free}</div>
                    <div className="text-center text-gray-300">
                      {item.monthly}
                    </div>
                    <div className="text-center text-gray-300">
                      {item.yearly}
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Frequently Asked Questions
            </h2>
          </div>

          <div className="space-y-6">
            {[
              {
                question: "Can I change my plan at any time?",
                answer:
                  "Yes, you can upgrade or downgrade your plan at any time. Changes take effect immediately, and we'll prorate any billing differences.",
              },
              {
                question: "What happens if I exceed my free plan limit?",
                answer:
                  "If you exceed the 60-minute limit on the free plan, you'll need to upgrade to continue processing files. Your existing processed files remain accessible.",
              },
              {
                question: "Do you offer refunds?",
                answer:
                  "We offer a 30-day money-back guarantee for all paid plans. If you're not satisfied, contact our support team for a full refund.",
              },
              {
                question: "Is there a discount for annual billing?",
                answer:
                  "Yes! Our yearly plan saves you $49 compared to paying monthly. That's a 45% discount on the annual subscription.",
              },
              {
                question: "What payment methods do you accept?",
                answer:
                  "We accept all major credit cards, PayPal, and bank transfers through our secure payment processor 2Checkout.",
              },
            ].map((faq, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: index * 0.1 }}
                className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-xl p-6"
              >
                <h3 className="text-lg font-semibold text-white mb-3">
                  {faq.question}
                </h3>
                <p className="text-gray-300">{faq.answer}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-gradient-to-r from-purple-900/50 to-pink-900/50">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">
            Ready to Get Started?
          </h2>
          <p className="text-xl text-gray-300 mb-8">
            Join thousands of content creators who trust SilenceCutter
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/auth/signup"
              className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-8 py-4 rounded-lg text-lg font-semibold hover:from-purple-600 hover:to-pink-600 transition-all"
            >
              Start Free Trial
            </Link>
            <Link
              href="/contact"
              className="border border-white/20 text-white px-8 py-4 rounded-lg text-lg font-semibold hover:bg-white/10 transition-all"
            >
              Contact Sales
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
