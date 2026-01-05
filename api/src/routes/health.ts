import { Router, Request, Response } from "express";
import { Connection } from "@solana/web3.js";
import { HealthResponse, API_VERSION } from "../types";

const startTime = Date.now();

export function createHealthRouter(connection: Connection): Router {
  const router = Router();

  router.get("/", async (_req: Request, res: Response) => {
    const uptime = Date.now() - startTime;
    let rpcConnected = false;
    let rpcSlot: number | null = null;
    let rpcLatencyMs = 0;

    const rpcStart = Date.now();
    try {
      rpcSlot = await connection.getSlot("confirmed");
      rpcConnected = true;
    } catch {
      rpcConnected = false;
    }
    rpcLatencyMs = Date.now() - rpcStart;

    const status: HealthResponse["status"] = rpcConnected
      ? rpcLatencyMs < 2000
        ? "healthy"
        : "degraded"
      : "unhealthy";

    const response: HealthResponse = {
      status,
      version: API_VERSION,
      uptime,
      solanaRpc: {
        connected: rpcConnected,
        slot: rpcSlot,
        latencyMs: rpcLatencyMs,
      },
      timestamp: Date.now(),
    };

    const httpStatus = status === "unhealthy" ? 503 : 200;
    res.status(httpStatus).json(response);
  });

  router.get("/ready", async (_req: Request, res: Response) => {
    try {
      const slot = await connection.getSlot("confirmed");
      res.json({ ready: true, slot, timestamp: Date.now() });
    } catch {
      res.status(503).json({ ready: false, timestamp: Date.now() });
    }
  });

  router.get("/live", (_req: Request, res: Response) => {
    res.json({
      alive: true,
      uptime: Date.now() - startTime,
      timestamp: Date.now(),
    });
  });

  return router;
}
