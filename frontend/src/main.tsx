import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./styles/index.css";
import { Disposicion } from "./components/Disposicion";
import { Dashboard } from "./pages/Dashboard";
import { CentroOperaciones } from "./pages/CentroOperaciones";
import { SolicitarServicio } from "./pages/SolicitarServicio";
import { Historial } from "./pages/Historial";
import { Configuracion } from "./pages/Configuracion";
import { Benchmarks } from "./pages/Benchmarks";
import { ErrorAplicacion } from "./pages/ErrorAplicacion";

const enrutador = createBrowserRouter(
  [
  {
    path: "/",
    element: <Disposicion />,
    errorElement: <ErrorAplicacion />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "operaciones", element: <CentroOperaciones /> },
      { path: "solicitar", element: <SolicitarServicio /> },
      { path: "historial", element: <Historial /> },
      { path: "configuracion", element: <Configuracion /> },
      { path: "benchmarks", element: <Benchmarks /> },
    ],
  },
  ],
  {
    future: {
      v7_relativeSplatPath: true,
      v7_fetcherPersist: true,
      v7_normalizeFormMethod: true,
      v7_partialHydration: true,
      v7_skipActionErrorRevalidation: true,
    },
  },
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={enrutador} future={{ v7_startTransition: true }} />
  </StrictMode>,
);
