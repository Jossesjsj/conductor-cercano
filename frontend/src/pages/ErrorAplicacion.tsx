import { useRouteError } from "react-router-dom";
import { Logo } from "@/components/Disposicion";

export function ErrorAplicacion() {
  const error = useRouteError() as Error | undefined;
  return (
    <div className="grid h-full place-items-center p-6">
      <div className="panel max-w-lg space-y-4 p-6 text-center">
        <div className="flex justify-center"><Logo /></div>
        <h1 className="text-lg font-semibold text-white">Se produjo un error en la interfaz</h1>
        <p className="text-sm text-slate-400">{error?.message ?? "Error desconocido"}</p>
        <a href="/" className="boton-primario">Volver al panel</a>
      </div>
    </div>
  );
}
