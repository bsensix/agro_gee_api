import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { FarmsPage } from "./features/farms/FarmsPage";
import { FieldsPage } from "./features/fields/FieldsPage";
import { UsersPage } from "./features/users/UsersPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/app/users" replace />} />
      <Route path="/app" element={<Layout />}>
        <Route index element={<Navigate to="users" replace />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="farms" element={<FarmsPage />} />
        <Route path="fields" element={<FieldsPage />} />
        <Route path="*" element={<Navigate to="/app/users" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/app/users" replace />} />
    </Routes>
  );
}
