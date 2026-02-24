import { createBrowserRouter } from "react-router-dom";

import AppShell from "./layout/AppShell";
import AdminPanel from "../pages/AdminPanel";
import BookDetailPage from "../pages/BookDetailPage";
import LandingPage from "../pages/LandingPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "book/:workId", element: <BookDetailPage /> },
      { path: "admin", element: <AdminPanel /> },
    ],
  },
]);
