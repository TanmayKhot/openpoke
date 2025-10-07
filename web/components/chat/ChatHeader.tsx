interface ChatHeaderProps {
  onOpenSettings: () => void;
  onMemoryReset: () => void;
  onToggleMemoryPause: () => void;
  isMemoryPaused: boolean;
}

export function ChatHeader({ onOpenSettings, onMemoryReset, onToggleMemoryPause, isMemoryPaused }: ChatHeaderProps) {
  return (
    <header className="mb-4 flex items-center justify-between">
      <div className="flex items-center">
        <h1 className="text-lg font-semibold">OpenPoke 🌴</h1>
      </div>
      <div className="flex items-center gap-2">
        <button
          className="rounded-md border border-gray-200 px-3 py-2 text-sm hover:bg-gray-50"
          onClick={onOpenSettings}
        >
          Settings
        </button>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Incognito</span>
          <button
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
              isMemoryPaused 
                ? 'bg-blue-600' 
                : 'bg-gray-200'
            }`}
            onClick={onToggleMemoryPause}
            title={isMemoryPaused ? 'Incognito Mode: ON - Conversations not saved' : 'Incognito Mode: OFF - Conversations saved'}
            role="switch"
            aria-checked={isMemoryPaused}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-lg transition-transform duration-200 ease-in-out ${
                isMemoryPaused ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
        <button
          className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 hover:bg-red-100"
          onClick={onMemoryReset}
          title="Reset all memory and cache"
        >
          Memory Reset
        </button>
      </div>
    </header>
  );
}
