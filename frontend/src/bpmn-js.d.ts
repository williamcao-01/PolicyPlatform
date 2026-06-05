declare module 'bpmn-js/lib/Viewer' {
  export default class BpmnViewer {
    constructor(options: { container: HTMLElement });
    importXML(xml: string): Promise<unknown>;
    get(name: string): unknown;
    destroy(): void;
  }
}

