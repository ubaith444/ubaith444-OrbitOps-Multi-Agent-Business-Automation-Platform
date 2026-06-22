import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex min-h-9 items-center justify-center gap-2 rounded-lg text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand)] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-[var(--brand)] text-[var(--brand-contrast)] shadow-sm hover:brightness-110",
        outline: "border hairline bg-[var(--surface)] text-[var(--text)] hover:bg-[var(--surface-subtle)] hover:text-[var(--text-strong)]",
        ghost: "text-muted hover:bg-[var(--surface-subtle)] hover:text-[var(--text-strong)]",
        danger: "bg-[var(--danger)] text-white hover:brightness-110",
      },
      size: { default: "px-3.5 py-2", sm: "min-h-8 px-2.5 py-1.5 text-xs", icon: "size-9" },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export function Button({
  className,
  variant,
  size,
  asChild,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
