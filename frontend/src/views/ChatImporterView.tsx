import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../services/api';
import { ChatInfo, EpisodePreview, ImportPreviewResponse, ImportStatusResponse } from '../types';

interface ChatImporterViewProps {
  chats: ChatInfo[];
  selectedChatId: number | null;
  onNavigateToGraph?: (chatId: number) => void;
}

export const ChatImporterView: React.FC<ChatImporterViewProps> = React.memo(
  ({ chats, selectedChatId, onNavigateToGraph }) => {
    // File state
    const [file, setFile] = useState<File | null>(null);
    const [fileJson, setFileJson] = useState<unknown | null>(null);
    const [isParsingJson, setIsParsingJson] = useState(false);
    const [fileReadProgress, setFileReadProgress] = useState<number>(0);
    const [fileReadStage, setFileReadStage] = useState<string>('');
    const [isDragging, setIsDragging] = useState(false);

    // Form settings
    const [targetChatId, setTargetChatId] = useState<string>(() =>
      selectedChatId ? String(selectedChatId) : ''
    );
    const [gapMinutes, setGapMinutes] = useState<number>(20);
    const [maxMessages, setMaxMessages] = useState<number>(15);
    const [delaySeconds, setDelaySeconds] = useState<number>(0.5);
    const [syncDb, setSyncDb] = useState<boolean>(true);

    // Preview state & analysis progress
    const [previewLoading, setPreviewLoading] = useState(false);
    const [previewSeconds, setPreviewSeconds] = useState<number>(0);
    const [previewProgress, setPreviewProgress] = useState<number>(0);
    const [previewStage, setPreviewStage] = useState<string>('');
    const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);

    // Ingestion state & polling
    const [statusData, setStatusData] = useState<ImportStatusResponse | null>(null);
    const [isStarting, setIsStarting] = useState(false);
    const pollIntervalRef = useRef<number | null>(null);

    // Animate preview analysis progress and stage transitions
    useEffect(() => {
      if (!previewLoading) {
        setPreviewSeconds(0);
        setPreviewProgress(0);
        setPreviewStage('');
        return;
      }

      setPreviewStage('Sending chat export payload to server...');
      setPreviewProgress(15);

      const startTime = Date.now();
      const interval = window.setInterval(() => {
        const elapsed = (Date.now() - startTime) / 1000;
        setPreviewSeconds(Math.round(elapsed * 10) / 10);

        if (elapsed <= 1.5) {
          setPreviewStage('Sending chat export payload to server...');
          setPreviewProgress(Math.min(30, Math.round(15 + elapsed * 10)));
        } else if (elapsed <= 4.0) {
          setPreviewStage('Validating export schema & parsing messages...');
          setPreviewProgress(Math.min(60, Math.round(30 + (elapsed - 1.5) * 12)));
        } else if (elapsed <= 8.0) {
          setPreviewStage('Filtering noise & system messages...');
          setPreviewProgress(Math.min(85, Math.round(60 + (elapsed - 4.0) * 6)));
        } else {
          setPreviewStage('Chunking dialogue episodes & extracting members...');
          setPreviewProgress(Math.min(95, Math.round(85 + (elapsed - 8.0) * 2)));
        }
      }, 100);

      return () => {
        window.clearInterval(interval);
      };
    }, [previewLoading]);

    // Sync selectedChatId with targetChatId if changed from selector
    useEffect(() => {
      if (selectedChatId && !targetChatId) {
        setTargetChatId(String(selectedChatId));
      }
    }, [selectedChatId, targetChatId]);

    // Handle file selection
    const handleFileSelected = useCallback((selectedFile: File) => {
      setErrorMsg(null);
      setPreviewData(null);
      if (!selectedFile.name.endsWith('.json')) {
        setErrorMsg('Please select a valid Telegram JSON export file (.json).');
        return;
      }

      setFile(selectedFile);
      setIsParsingJson(true);
      setFileReadProgress(0);
      setFileReadStage('Reading file from disk...');

      const reader = new FileReader();

      reader.onprogress = (e) => {
        if (e.lengthComputable && e.total > 0) {
          const pct = Math.round((e.loaded / e.total) * 100);
          setFileReadProgress(pct);
          const loadedMB = (e.loaded / (1024 * 1024)).toFixed(1);
          const totalMB = (e.total / (1024 * 1024)).toFixed(1);
          setFileReadStage(`Reading file: ${pct}% (${loadedMB}/${totalMB} MB)...`);
        }
      };

      reader.onload = (e) => {
        setFileReadProgress(100);
        setFileReadStage('Parsing JSON structure into memory...');

        // Yield slightly so browser renders stage text before JSON.parse executes
        window.setTimeout(() => {
          try {
            const content = e.target?.result as string;
            const parsed = JSON.parse(content);
            setFileJson(parsed);

            // Auto-detect chat ID from export if not specified
            if (parsed && typeof parsed === 'object') {
              const expId = (parsed as { id?: number | string }).id;
              if (expId) {
                const numId = Number(expId);
                if (!isNaN(numId)) {
                  const autoId = numId > 0 ? (String(numId).startsWith('100') ? -numId : -Number(`100${numId}`)) : numId;
                  setTargetChatId(String(autoId));
                }
              }
            }
          } catch (err) {
            setErrorMsg('Failed to parse JSON file. Ensure it is a valid Telegram export.');
            setFile(null);
            setFileJson(null);
          } finally {
            setIsParsingJson(false);
            setFileReadStage('');
          }
        }, 50);
      };
      reader.readAsText(selectedFile);
    }, []);

    // Drag-and-drop handlers
    const handleDragOver = useCallback((e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
    }, []);

    const handleDrop = useCallback(
      (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleFileSelected(e.dataTransfer.files[0]);
        }
      },
      [handleFileSelected]
    );

    // Run Dry-Run Preview
    const handleRunPreview = async () => {
      if (!fileJson) {
        setErrorMsg('Please select a Telegram export JSON file first.');
        return;
      }

      setErrorMsg(null);
      setPreviewLoading(true);
      try {
        const chatIdVal = targetChatId.trim() ? parseInt(targetChatId.trim(), 10) : null;
        const res = await api.previewImport({
          data: fileJson,
          chat_id: chatIdVal,
          gap_minutes: gapMinutes,
          max_messages: maxMessages,
        });
        setPreviewData(res);
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : String(err);
        setErrorMsg(`Preview failed: ${msg}`);
      } finally {
        setPreviewLoading(false);
      }
    };

    // Poll status helper
    const pollStatus = useCallback(async () => {
      try {
        const status = await api.getImportStatus();
        setStatusData(status);

        if (status.status !== 'running') {
          if (pollIntervalRef.current) {
            window.clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
        }
      } catch (err) {
        // Silently tolerate transient polling errors
      }
    }, []);

    // Start background ingestion
    const handleStartImport = async () => {
      if (!fileJson) {
        setErrorMsg('Please select a file to import.');
        return;
      }

      setErrorMsg(null);
      setIsStarting(true);
      try {
        const chatIdVal = targetChatId.trim() ? parseInt(targetChatId.trim(), 10) : null;
        const initialStatus = await api.startImport({
          data: fileJson,
          chat_id: chatIdVal,
          gap_minutes: gapMinutes,
          max_messages: maxMessages,
          delay: delaySeconds,
          no_db: !syncDb,
        });
        setStatusData(initialStatus);

        // Start polling
        if (!pollIntervalRef.current) {
          pollIntervalRef.current = window.setInterval(pollStatus, 1500);
        }
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : String(err);
        setErrorMsg(`Failed to start import: ${msg}`);
      } finally {
        setIsStarting(false);
      }
    };

    // Cancel import
    const handleCancelImport = async () => {
      try {
        await api.cancelImport();
        await pollStatus();
      } catch (err) {
        // Ignored
      }
    };

    // Initial status check on mount
    useEffect(() => {
      pollStatus();
      return () => {
        if (pollIntervalRef.current) {
          window.clearInterval(pollIntervalRef.current);
        }
      };
    }, [pollStatus]);

    const isRunning = statusData?.status === 'running';

    return (
      <div className="p-6 space-y-6 max-w-7xl mx-auto overflow-y-auto">
        {/* Header */}
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide flex items-center space-x-2">
            <span>📥</span>
            <span>Telegram Chat History Importer</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Import Telegram Desktop JSON chat exports into Graphiti temporal knowledge graph & PostgreSQL
          </p>
        </div>

        {/* Error notification banner */}
        {errorMsg && (
          <div className="p-4 bg-rose-950/60 border border-rose-800 text-rose-300 rounded-xl text-xs flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span>⚠️</span>
              <span>{errorMsg}</span>
            </div>
            <button
              onClick={() => setErrorMsg(null)}
              className="text-rose-400 hover:text-white text-xs font-semibold cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Live Ingestion Status Banner if active */}
        {isRunning && (
          <div className="bg-sky-950/50 border border-sky-800/80 rounded-2xl p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <span className="w-3 h-3 rounded-full bg-sky-400 animate-ping" />
                <span className="text-sm font-bold text-white">Import In Progress</span>
              </div>
              <button
                onClick={handleCancelImport}
                className="px-3 py-1 bg-rose-600/30 hover:bg-rose-600/50 text-rose-200 border border-rose-600 rounded-lg text-xs font-semibold cursor-pointer transition"
              >
                Cancel Import
              </button>
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-300">
                <span>{statusData?.current_stage}</span>
                <span className="font-mono font-bold text-sky-400">
                  {statusData?.processed_episodes} / {statusData?.total_episodes} ({statusData?.progress_percent}%)
                </span>
              </div>
              <div className="w-full bg-slate-900 rounded-full h-2.5 overflow-hidden border border-slate-800">
                <div
                  className="bg-sky-500 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${statusData?.progress_percent || 0}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Success Banner if just finished */}
        {statusData?.status === 'completed' && statusData.last_summary && (
          <div className="bg-emerald-950/50 border border-emerald-800 rounded-2xl p-5 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <span className="text-2xl">🎉</span>
              <div>
                <div className="text-sm font-bold text-emerald-300">Import Successfully Completed!</div>
                <div className="text-xs text-slate-300 mt-0.5">
                  Ingested {statusData.last_summary.total_episodes} dialogue episodes ({statusData.last_summary.messages_ingested} messages) into Graphiti.
                </div>
              </div>
            </div>
            {onNavigateToGraph && (
              <button
                onClick={() => onNavigateToGraph(statusData.last_summary!.chat_id)}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold cursor-pointer transition shadow-sm"
              >
                View in Knowledge Graph 🕸️
              </button>
            )}
          </div>
        )}

        {/* Ingestion Failure Banner */}
        {statusData?.status === 'failed' && (
          <div className="bg-rose-950/70 border border-rose-800 rounded-2xl p-5 flex items-start justify-between shadow-lg">
            <div className="flex items-start space-x-3.5">
              <span className="text-2xl mt-0.5">❌</span>
              <div className="space-y-1">
                <div className="text-sm font-bold text-rose-300">Graphiti Import Failed</div>
                <div className="text-xs text-rose-200 leading-relaxed font-mono">
                  {statusData.error || statusData.current_stage || 'Unknown error occurred during ingestion.'}
                </div>
                <div className="text-[11px] text-slate-400 pt-1">
                  Progress before failure: {statusData.processed_episodes} / {statusData.total_episodes} episodes.
                  {statusData.finished_at && ` (at ${new Date(statusData.finished_at).toLocaleTimeString()})`}
                </div>
              </div>
            </div>
            <button
              onClick={() => setStatusData(null)}
              className="px-3 py-1 bg-rose-900/60 hover:bg-rose-800 text-rose-200 rounded-lg text-xs font-semibold cursor-pointer transition shrink-0 ml-4"
            >
              Dismiss
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Dropzone & File selection */}
          <div className="lg:col-span-1 space-y-4">
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-2xl p-6 text-center transition cursor-pointer flex flex-col items-center justify-center min-h-[220px] ${
                isDragging
                  ? 'border-sky-500 bg-sky-950/30'
                  : file
                  ? 'border-emerald-600/80 bg-slate-900/90'
                  : 'border-slate-800 hover:border-slate-700 bg-slate-900/40'
              }`}
              onClick={() => {
                const input = document.getElementById('json-file-input') as HTMLInputElement;
                if (input) input.click();
              }}
            >
              <input
                id="json-file-input"
                type="file"
                accept=".json"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileSelected(e.target.files[0]);
                  }
                }}
              />

              <div className="text-3xl mb-2">{file ? '📄' : '📁'}</div>
              {file ? (
                <div className="space-y-2 w-full max-w-[240px]">
                  <div className="text-xs font-bold text-emerald-400 truncate text-center">{file.name}</div>
                  <div className="text-[11px] text-slate-400 font-mono text-center">
                    {(file.size / (1024 * 1024)).toFixed(2)} MB
                  </div>
                  {isParsingJson && (
                    <div className="space-y-1.5 pt-1">
                      <div className="flex justify-between items-center text-[10px] text-sky-400 font-medium">
                        <span className="truncate max-w-[170px]">{fileReadStage || 'Reading file...'}</span>
                        <span className="font-mono">{fileReadProgress}%</span>
                      </div>
                      <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden border border-slate-800">
                        <div
                          className="bg-sky-500 h-1.5 rounded-full transition-all duration-200"
                          style={{ width: `${fileReadProgress}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-1">
                  <div className="text-xs font-bold text-slate-200">Drag & drop result.json here</div>
                  <div className="text-[11px] text-slate-400">or click to browse from disk</div>
                  <div className="text-[10px] text-slate-500 mt-2">Exported from Telegram Desktop in JSON format</div>
                </div>
              )}
            </div>

            {/* Ingestion Parameters Form Card */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider text-slate-400">
                Import Parameters
              </h3>

              <div className="space-y-3 text-xs">
                <div>
                  <label className="text-slate-300 block mb-1 font-medium">Target Chat ID:</label>
                  <input
                    type="text"
                    value={targetChatId}
                    onChange={(e) => setTargetChatId(e.target.value)}
                    placeholder="e.g. -1001234567890"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-sky-500"
                  />
                  <span className="text-[10px] text-slate-500 block mt-0.5">
                    Telegram supergroup identifier with -100 prefix
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-slate-300 block mb-1 font-medium">Idle Gap (min):</label>
                    <input
                      type="number"
                      min={1}
                      max={120}
                      value={gapMinutes}
                      onChange={(e) => setGapMinutes(parseInt(e.target.value, 10) || 20)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-sky-500"
                    />
                  </div>
                  <div>
                    <label className="text-slate-300 block mb-1 font-medium">Max Messages:</label>
                    <input
                      type="number"
                      min={1}
                      max={50}
                      value={maxMessages}
                      onChange={(e) => setMaxMessages(parseInt(e.target.value, 10) || 15)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-sky-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-slate-300 block mb-1 font-medium">API Delay (seconds):</label>
                  <input
                    type="number"
                    step={0.1}
                    min={0}
                    max={10}
                    value={delaySeconds}
                    onChange={(e) => setDelaySeconds(parseFloat(e.target.value) || 0.0)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-sky-500"
                  />
                  <span className="text-[10px] text-slate-500 block mt-0.5">
                    Rate-limiting throttle between OpenAI / Graphiti calls
                  </span>
                </div>

                <div className="flex items-center space-x-2 pt-1">
                  <input
                    id="sync-db-chk"
                    type="checkbox"
                    checked={syncDb}
                    onChange={(e) => setSyncDb(e.target.checked)}
                    className="rounded bg-slate-950 border-slate-800 text-sky-600 focus:ring-sky-500 cursor-pointer"
                  />
                  <label htmlFor="sync-db-chk" className="text-slate-300 cursor-pointer">
                    Sync members to PostgreSQL
                  </label>
                </div>
              </div>

              <div className="pt-2 flex flex-col space-y-2">
                <button
                  onClick={handleRunPreview}
                  disabled={!fileJson || previewLoading || isRunning}
                  className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold transition flex items-center justify-center space-x-2 cursor-pointer ${
                    !fileJson || previewLoading || isRunning
                      ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                      : 'bg-sky-600 hover:bg-sky-500 text-white shadow-sm'
                  }`}
                >
                  {previewLoading ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                      <span>Analyzing ({previewSeconds.toFixed(1)}s)...</span>
                    </>
                  ) : (
                    <>
                      <span>🔍</span>
                      <span>Run Dry-Run Preview</span>
                    </>
                  )}
                </button>

                {previewData && (
                  <button
                    onClick={handleStartImport}
                    disabled={isStarting || isRunning}
                    className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold transition flex items-center justify-center space-x-2 cursor-pointer ${
                      isStarting || isRunning
                        ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                        : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm'
                    }`}
                  >
                    {isStarting ? (
                      <>
                        <span className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                        <span>Starting...</span>
                      </>
                    ) : (
                      <>
                        <span>🚀</span>
                        <span>Start Graphiti Ingestion</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Right Column: Preview Statistics & Sample Episodes */}
          <div className="lg:col-span-2 space-y-4">
            {previewLoading ? (
              <div className="bg-slate-900 border border-sky-800/60 rounded-2xl p-8 flex flex-col items-center justify-center min-h-[420px] space-y-6 shadow-xl">
                <div className="relative flex items-center justify-center">
                  <div className="w-20 h-20 rounded-full border-4 border-sky-500/20 border-t-sky-400 animate-spin" />
                  <span className="absolute text-2xl animate-pulse">⚡</span>
                </div>

                <div className="text-center space-y-2 max-w-md">
                  <div className="text-base font-bold text-white flex items-center justify-center space-x-2">
                    <span>Analyzing Chat Export</span>
                    <span className="px-2.5 py-0.5 bg-sky-950 border border-sky-800 text-sky-300 text-xs rounded-full font-mono">
                      {previewSeconds.toFixed(1)}s
                    </span>
                  </div>
                  <p className="text-xs text-sky-300 font-medium">
                    {previewStage || 'Processing Telegram messages...'}
                  </p>
                </div>

                {/* Animated Progress Bar */}
                <div className="w-full max-w-md space-y-2">
                  <div className="w-full bg-slate-950 rounded-full h-3 overflow-hidden border border-slate-800 relative">
                    <div
                      className="bg-gradient-to-r from-sky-500 via-indigo-500 to-sky-400 h-3 rounded-full transition-all duration-300 ease-out"
                      style={{ width: `${previewProgress}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[11px] text-slate-400 font-mono">
                    <span>Dry-run analysis pipeline</span>
                    <span className="text-sky-400 font-bold">{previewProgress}%</span>
                  </div>
                </div>

                {/* Stage checklist / indicators */}
                <div className="w-full max-w-md bg-slate-950/70 border border-slate-800/80 rounded-xl p-3.5 space-y-2 text-xs">
                  <div className="flex items-center space-x-2">
                    <span className={previewProgress >= 30 ? 'text-emerald-400 font-bold' : 'text-slate-500'}>
                      {previewProgress >= 30 ? '✓' : '○'}
                    </span>
                    <span className={previewProgress >= 30 ? 'text-slate-200' : 'text-slate-500'}>
                      Payload transmission & schema validation
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={previewProgress >= 60 ? 'text-emerald-400 font-bold' : 'text-slate-500'}>
                      {previewProgress >= 60 ? '✓' : '○'}
                    </span>
                    <span className={previewProgress >= 60 ? 'text-slate-200' : 'text-slate-500'}>
                      Noise filtering & service message removal
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={previewProgress >= 85 ? 'text-emerald-400 font-bold' : 'text-slate-500'}>
                      {previewProgress >= 85 ? '✓' : '○'}
                    </span>
                    <span className={previewProgress >= 85 ? 'text-slate-200' : 'text-slate-500'}>
                      Dialogue chunking & member discovery
                    </span>
                  </div>
                </div>

                <div className="text-[11px] text-slate-500 bg-slate-950/50 border border-slate-800/50 rounded-xl px-4 py-2 max-w-md text-center">
                  💡 <span className="text-slate-400 font-medium">Safe dry-run:</span> No database writes or LLM tokens are consumed during preview analysis.
                </div>
              </div>
            ) : previewData ? (
              <div className="space-y-4">
                {/* Metric Summary Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                    <div className="text-slate-400">Total Messages</div>
                    <div className="text-lg font-bold text-white mt-1 font-mono">
                      {previewData.total_raw_messages.toLocaleString()}
                    </div>
                  </div>
                  <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                    <div className="text-slate-400">Meaningful Content</div>
                    <div className="text-lg font-bold text-emerald-400 mt-1 font-mono">
                      {previewData.meaningful_messages.toLocaleString()}
                    </div>
                  </div>
                  <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                    <div className="text-slate-400">Filtered Noise</div>
                    <div className="text-lg font-bold text-amber-400 mt-1 font-mono flex items-center space-x-1.5">
                      <span>{previewData.dropped_noise_messages.toLocaleString()}</span>
                      <span className="text-[10px] text-amber-500 font-normal">
                        ({previewData.noise_percentage}%)
                      </span>
                    </div>
                  </div>
                  <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                    <div className="text-slate-400">Graphiti Episodes</div>
                    <div className="text-lg font-bold text-purple-400 mt-1 font-mono">
                      {previewData.total_episodes.toLocaleString()}
                    </div>
                  </div>
                </div>

                {/* Chat and Member details */}
                <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-2 text-xs">
                  <div className="flex justify-between items-center">
                    <div className="font-bold text-white flex items-center space-x-2">
                      <span>💬</span>
                      <span>{previewData.chat_title}</span>
                      <span className="text-slate-400 font-normal font-mono">({previewData.chat_id})</span>
                    </div>
                    <span className="text-slate-400">
                      {previewData.members_count} Discovered Members
                    </span>
                  </div>

                  {/* Member badges */}
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {previewData.members.map((m) => (
                      <span
                        key={m.user_id}
                        className="px-2 py-0.5 bg-slate-950 border border-slate-800 text-slate-300 rounded-md text-[11px] font-mono"
                      >
                        {m.display_name}
                      </span>
                    ))}
                    {previewData.members_count > previewData.members.length && (
                      <span className="px-2 py-0.5 text-slate-500 text-[11px]">
                        +{previewData.members_count - previewData.members.length} more
                      </span>
                    )}
                  </div>
                </div>

                {/* Sample Episodes Preview */}
                <div className="space-y-3">
                  <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                    Dialogue Episodes Preview (First {previewData.sample_episodes.length} of {previewData.total_episodes})
                  </div>

                  <div className="space-y-3">
                    {previewData.sample_episodes.map((ep: EpisodePreview) => (
                      <div
                        key={ep.episode_index}
                        className="p-4 bg-slate-900/90 border border-slate-800 rounded-xl space-y-2 text-xs"
                      >
                        <div className="flex justify-between items-center border-b border-slate-800 pb-2">
                          <div className="flex items-center space-x-2">
                            <span className="px-2 py-0.5 bg-sky-950 text-sky-300 border border-sky-800 rounded font-mono font-bold text-[10px]">
                              Episode #{ep.episode_index + 1}
                            </span>
                            <span className="text-slate-400 font-medium">Author: {ep.source_user_name}</span>
                          </div>
                          <span className="text-[11px] text-slate-400 font-mono">
                            {new Date(ep.reference_time).toLocaleString()}
                          </span>
                        </div>
                        <pre className="text-slate-200 font-sans text-xs whitespace-pre-wrap bg-slate-950 p-3 rounded-lg border border-slate-800/60 leading-relaxed">
                          {ep.text}
                        </pre>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-12 text-center flex flex-col items-center justify-center min-h-[350px] space-y-3">
                <span className="text-4xl text-slate-600">📊</span>
                <div className="text-sm font-bold text-slate-400">No Export Preview Loaded</div>
                <p className="text-xs text-slate-500 max-w-sm">
                  Upload a Telegram export JSON file on the left and click &quot;Run Dry-Run Preview&quot; to inspect noise filtering, chunking statistics, and sample episodes.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
);
