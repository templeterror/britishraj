// jsdom lacks the layout APIs React Flow measures nodes with. These stand-ins follow the
// "Testing" guide of @xyflow/react: every element reports a 1px box unless it has an inline size.

class ResizeObserverStub {
  private readonly callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }

  observe(target: Element) {
    const el = target as HTMLElement;
    const contentRect = { x: 0, y: 0, width: el.offsetWidth, height: el.offsetHeight } as DOMRectReadOnly;
    this.callback([{ target, contentRect } as ResizeObserverEntry], this as unknown as ResizeObserver);
  }

  unobserve() {}

  disconnect() {}
}

class DOMMatrixReadOnlyStub {
  m22: number;

  constructor(transform?: string) {
    const scale = transform?.match(/scale\(([1-9.]+)\)/)?.[1];
    this.m22 = scale !== undefined ? Number(scale) : 1;
  }
}

let installed = false;

export function installReactFlowJsdom(): void {
  if (installed) return;
  installed = true;
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
  globalThis.DOMMatrixReadOnly = DOMMatrixReadOnlyStub as unknown as typeof DOMMatrixReadOnly;
  Object.defineProperties(HTMLElement.prototype, {
    offsetHeight: {
      get(this: HTMLElement) {
        return parseFloat(this.style.height) || 1;
      },
    },
    offsetWidth: {
      get(this: HTMLElement) {
        return parseFloat(this.style.width) || 1;
      },
    },
  });
  (SVGElement.prototype as unknown as { getBBox: () => DOMRect }).getBBox = () =>
    ({ x: 0, y: 0, width: 0, height: 0 }) as DOMRect;
}
