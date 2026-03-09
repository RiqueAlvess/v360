import { redirect } from "next/navigation";
import { ROUTES } from "@/lib/constants";

// Root redirect — middleware handles auth, but redirect as default
export default function RootPage() {
  redirect(ROUTES.DASHBOARD);
}
