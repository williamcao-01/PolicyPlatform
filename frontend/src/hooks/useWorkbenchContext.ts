import { useMemo, useState } from 'react';
import type { WorkbenchContext } from '../types';

export function useWorkbenchContext() {
  const [policyIds, setPolicyIds] = useState<string[]>([]);
  const [processIds, setProcessIds] = useState<string[]>([]);

  const context = useMemo<WorkbenchContext>(
    () => ({ policyIds, processIds }),
    [policyIds, processIds]
  );

  function togglePolicy(id: string) {
    setPolicyIds((items) => (items.includes(id) ? items.filter((item) => item !== id) : [...items, id]));
  }

  function toggleProcess(id: string) {
    setProcessIds((items) => (items.includes(id) ? items.filter((item) => item !== id) : [id]));
  }

  function removePolicy(id: string) {
    setPolicyIds((items) => items.filter((item) => item !== id));
  }

  function removeProcess(id: string) {
    setProcessIds((items) => items.filter((item) => item !== id));
  }

  return {
    context,
    togglePolicy,
    toggleProcess,
    removePolicy,
    removeProcess
  };
}
