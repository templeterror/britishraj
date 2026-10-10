import { clerkMiddleware } from "@clerk/nextjs/server";

// Runs on every request. By default it does not block anything; routes are
// made protected with auth.protect() inside the route itself (see
// app/page.tsx), which keeps this file simple as more pages are added.
export default clerkMiddleware();

export const config = {
  matcher: [
    // Skip Next.js internals and static files, unless found in search params
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
  ],
};
