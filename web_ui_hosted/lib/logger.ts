/**
 * Structured logger for Next.js API routes and components
 * Outputs JSON logs with level, timestamp, and context data
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  level: LogLevel;
  msg: string;
  ts: string;
  route?: string;
  [key: string]: unknown;
}

const formatLog = (level: LogLevel, msg: string, data?: Record<string, unknown>): string => {
  const entry: LogEntry = {
    level,
    msg,
    ts: new Date().toISOString(),
    ...data
  };
  return JSON.stringify(entry);
};

export const logger = {
  debug: (msg: string, data?: Record<string, unknown>) => {
    if (process.env.NODE_ENV === 'development') {
      console.log(formatLog('debug', msg, data));
    }
  },
  info: (msg: string, data?: Record<string, unknown>) => {
    console.log(formatLog('info', msg, data));
  },
  warn: (msg: string, data?: Record<string, unknown>) => {
    console.warn(formatLog('warn', msg, data));
  },
  error: (msg: string, data?: Record<string, unknown>) => {
    console.error(formatLog('error', msg, data));
  }
};

/**
 * Create a logger scoped to a specific route/component
 */
export const createLogger = (route: string) => ({
  debug: (msg: string, data?: Record<string, unknown>) => logger.debug(msg, { route, ...data }),
  info: (msg: string, data?: Record<string, unknown>) => logger.info(msg, { route, ...data }),
  warn: (msg: string, data?: Record<string, unknown>) => logger.warn(msg, { route, ...data }),
  error: (msg: string, data?: Record<string, unknown>) => logger.error(msg, { route, ...data })
});
