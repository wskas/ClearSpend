import { Navigate, useLocation } from "react-router-dom";
import { isAuthenticated } from "../../lib/auth.js";

// Route guard. Redirects to /login when there's no token, remembering where
// the user was headed so LoginPage can send them back after authenticating.
export default function RequireAuth({ children }) {
  const location = useLocation();

  if (!isAuthenticated()) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}
