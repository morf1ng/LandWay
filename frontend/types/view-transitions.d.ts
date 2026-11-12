export {};

declare global {
  interface ViewTransition {
    finished: Promise<void>;
    skipTransition: () => void;
    updateCallbackDone: Promise<void>;
    ready: Promise<void>;
  }

  interface Document {
    startViewTransition?: (callback: () => void) => ViewTransition;
  }
}
