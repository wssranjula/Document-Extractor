import { Route, Routes } from "react-router-dom";
import { AppShell } from "./AppShell";
import { JobPage } from "./pages/Job";
import { ReferenceUploadPage } from "./pages/ReferenceUpload";
import { SignInPage } from "./pages/SignIn";
import { UploadPage } from "./pages/Upload";

// Sign-in is public. The other pages sit inside the signed-in header.

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<SignInPage />} />
      <Route element={<AppShell />}>
        <Route path="/" element={<UploadPage />} />
        <Route path="/references/new" element={<ReferenceUploadPage />} />
        <Route path="/jobs/:jobId" element={<JobPage />} />
      </Route>
    </Routes>
  );
}
