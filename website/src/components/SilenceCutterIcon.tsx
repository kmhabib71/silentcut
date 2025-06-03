import React from "react";

interface SilenceCutterIconProps {
  className?: string;
  size?: number;
}

export const SilenceCutterIcon: React.FC<SilenceCutterIconProps> = ({
  className = "w-5 h-5 text-white",
  size = 24,
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
  </svg>
);

export default SilenceCutterIcon;
