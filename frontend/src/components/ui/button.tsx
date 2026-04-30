import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex h-10 items-center justify-center gap-2 whitespace-nowrap rounded-xl px-4 text-sm font-semibold transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-blue-600 text-white shadow-sm shadow-blue-100 hover:bg-blue-700",
        outline:
          "border border-slate-200 bg-white text-slate-700 shadow-sm shadow-slate-100 hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700",
        secondary:
          "border border-blue-100 bg-blue-50 text-blue-700 shadow-sm shadow-blue-50 hover:border-blue-200 hover:bg-blue-100",
        ghost: "text-slate-600 hover:bg-blue-50 hover:text-blue-700",
        danger:
          "border border-rose-200 bg-rose-50 text-rose-700 hover:border-rose-300 hover:bg-rose-100"
      }
    },
    defaultVariants: {
      variant: "default"
    }
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
