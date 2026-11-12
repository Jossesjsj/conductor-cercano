import { create } from "zustand";

export interface Notificacion {
  id: number;
  tipo: "exito" | "error" | "info";
  texto: string;
}

interface EstadoNotificaciones {
  lista: Notificacion[];
  notificar: (tipo: Notificacion["tipo"], texto: string) => void;
  descartar: (id: number) => void;
}

let secuencia = 0;

export const usarNotificaciones = create<EstadoNotificaciones>((set, get) => ({
  lista: [],
  notificar: (tipo, texto) => {
    const id = ++secuencia;
    set((s) => ({ lista: [...s.lista, { id, tipo, texto }].slice(-4) }));
    window.setTimeout(() => get().descartar(id), tipo === "error" ? 7000 : 4000);
  },
  descartar: (id) => set((s) => ({ lista: s.lista.filter((n) => n.id !== id) })),
}));

export const notificar = (tipo: Notificacion["tipo"], texto: string) => usarNotificaciones.getState().notificar(tipo, texto);
