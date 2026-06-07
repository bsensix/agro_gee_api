import { NavLink, Outlet } from "react-router-dom";

export function Layout() {
  return (
    <div className="layout">
      <nav aria-label="Main navigation">
        <NavLink to="/app/users">Users</NavLink>
        <NavLink to="/app/farms">Farms</NavLink>
        <NavLink to="/app/fields">Geometries</NavLink>
      </nav>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
