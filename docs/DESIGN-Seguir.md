---
name: Ethereal Finance
colors:
  surface: '#fcf9f8'
  surface-dim: '#dcd9d9'
  surface-bright: '#fcf9f8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3f2'
  surface-container: '#f0edec'
  surface-container-high: '#ebe7e7'
  surface-container-highest: '#e5e2e1'
  on-surface: '#1c1b1b'
  on-surface-variant: '#474555'
  inverse-surface: '#313030'
  inverse-on-surface: '#f3f0ef'
  outline: '#787587'
  outline-variant: '#c9c4d8'
  surface-tint: '#5b3de5'
  primary: '#4f2cd9'
  on-primary: '#ffffff'
  primary-container: '#684cf2'
  on-primary-container: '#efe9ff'
  inverse-primary: '#c8bfff'
  secondary: '#a300b9'
  on-secondary: '#ffffff'
  secondary-container: '#ec5dfe'
  on-secondary-container: '#5c0069'
  tertiary: '#941289'
  on-tertiary: '#ffffff'
  tertiary-container: '#b234a4'
  on-tertiary-container: '#ffe5f5'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e5deff'
  primary-fixed-dim: '#c8bfff'
  on-primary-fixed: '#190064'
  on-primary-fixed-variant: '#4317ce'
  secondary-fixed: '#ffd6fc'
  secondary-fixed-dim: '#fcaaff'
  on-secondary-fixed: '#36003e'
  on-secondary-fixed-variant: '#7c008d'
  tertiary-fixed: '#ffd7f2'
  tertiary-fixed-dim: '#ffacec'
  on-tertiary-fixed: '#390035'
  on-tertiary-fixed-variant: '#83007a'
  background: '#fcf9f8'
  on-background: '#1c1b1b'
  surface-variant: '#e5e2e1'
typography:
  display-lg:
    fontFamily: Hanken Grotesk
    fontSize: 64px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 40px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 28px
    fontWeight: '500'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Manrope
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Manrope
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  label-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.0'
    letterSpacing: 0.05em
  mono-data:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.4'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  container-max: 1280px
  gutter: 24px
  margin-desktop: 64px
  margin-mobile: 20px
  section-gap: 120px
---

## Brand & Style

This design system embodies a **Modern, Premium, and Minimalist** aesthetic tailored for a high-end financial platform. The brand personality is sophisticated yet technologically advanced, blending the precision of fintech with the fluidity of AI.

The visual direction utilizes a hybrid of **Minimalism** and **Glassmorphism**. It relies on expansive white space to denote luxury and clarity, while employing translucent, blurred layers to represent complex AI-driven data. The emotional response should be one of "effortless control"—feeling both high-status and intuitively simple. High-contrast accents in violet and pink serve as functional beacons within a serene, airy environment.

## Colors

The palette is anchored by a deep "Obsidian" neutral and a "Pure White" base, allowing the vibrant violets and magentas to pop. 

- **Primary (#684CF2):** Used for primary actions and core brand moments.
- **Secondary (#DF50F2):** Reserved for high-energy CTAs and interactive highlights.
- **AI Components:** Utilize a signature gradient moving from #684CF2 to #DF50F2 to signify intelligence and processing.
- **Dark Mode Contexts:** In app environments, the background shifts to #0D0D0D with surfaces utilizing #361340 to maintain depth and premium feel. 
- **Functional Accents:** Use #B133A3 for secondary interactive states and #341539 for subtle border or background depth in dark contexts.

## Typography

The typography strategy balances "Elegant" and "Technological." 

**Hanken Grotesk** is used for headlines to provide a sharp, contemporary edge that feels authoritative yet fresh. **Manrope** handles body copy, offering superior readability with a warm, modern touch. **Geist** is introduced for labels and data-heavy financial readouts to reinforce the developer-grade precision of the platform.

For mobile, display sizes are aggressively scaled down to maintain legibility without overwhelming the viewport. High contrast in weights (Bold for headers vs Regular for body) is essential to maintain hierarchy in a minimalist layout.

## Layout & Spacing

This design system employs a **fixed grid** model for the landing page and a **fluid container** model for the dashboard application.

- **Grid:** A 12-column grid with a 24px gutter.
- **Whitespace:** Use "Section Gaps" (120px+) liberally to separate brand stories and product features.
- **Rhythm:** All spacing is based on an 8px base unit. 
- **Desktop:** 64px outer margins provide a spacious, "gallery" feel.
- **Mobile:** Transition to a 4-column layout with 20px margins. Content should stack vertically, prioritizing financial snapshots and quick actions.

## Elevation & Depth

Hierarchy is achieved through **Tonal Layers** and **Minimalist Shadows**. 

1. **Base:** Pure #FFFFFF (Light) or #0D0D0D (Dark).
2. **Cards:** Use a 1px border (#DF50F2 at 10% opacity) rather than heavy shadows.
3. **Floating Elements:** For modals or primary dropdowns, use a very soft, highly diffused shadow: `box-shadow: 0 20px 40px rgba(0,0,0,0.04)`.
4. **AI/Interactive Glass:** Use a backdrop-filter (`blur(12px)`) with a semi-transparent violet tint to create a "glass" effect for floating AI insights, making them feel like they exist on a separate plane of intelligence.

## Shapes

The shape language is **Rounded**, reflecting the "moderate border radius" requirement. 

- **Standard (8px):** Applied to input fields, secondary buttons, and small cards.
- **Large (16px):** Applied to main feature containers and dashboard modules.
- **Extra Large (24px):** Applied to hero sections and prominent marketing cards.
- **Full Pill:** Exclusively reserved for status tags (e.g., "Active," "Pending") and the primary AI "Command Bar."

## Components

- **Buttons:** 
    - *Primary:* Solid #684CF2 with white text. High-radius (8px). 
    - *AI Action:* Gradient (#684CF2 to #DF50F2) with a subtle outer glow on hover.
- **Input Fields:** Minimalist approach. Only a bottom border in #0D0D0D (Light) or white (Dark) that transforms into a #DF50F2 1px solid box on focus.
- **Chips/Tags:** Small, Geist font, uppercase. Backgrounds should be 10% opacity versions of the primary/secondary colors.
- **Cards:** White background, 1px #E0E0E0 border, 16px radius. In dark mode, #361340 background with no border.
- **Progress Bars:** Use the AI gradient to represent wealth growth or data processing.
- **Financial Lists:** High vertical padding (16px+) between rows, using Geist for numerical data to ensure alignment and clarity.