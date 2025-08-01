import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { createRoot } from 'react-dom/client';

// Utility functions
const debounce = (func, delay) => {
  let timeoutId;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      func.apply(this, args);
    }, delay);
  };
};

const formatDuration = (start, end) => {
  const duration = (new Date(end) - new Date(start)) / 1000;
  const minutes = Math.floor(duration / 60);
  const seconds = Math.floor(duration % 60);
  return minutes > 0 ? `${minutes}м ${seconds}с` : `${seconds}с`;
};

const formatDate = (dateString) => {
  return new Date(dateString).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

// Icons as SVG components
const SearchIcon = () => React.createElement("svg", {
  fill: "none",
  stroke: "currentColor",
  viewBox: "0 0 24 24",
  className: "search-icon"
}, React.createElement("path", {
  strokeLinecap: "round",
  strokeLinejoin: "round",
  strokeWidth: 2,
  d: "m21 21-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0z"
}));

const DownloadIcon = () => React.createElement("svg", {
  fill: "none",
  stroke: "currentColor",
  viewBox: "0 0 24 24",
  width: "16",
  height: "16"
}, React.createElement("path", {
  strokeLinecap: "round",
  strokeLinejoin: "round",
  strokeWidth: 2,
  d: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
}));

const BookIcon = () => React.createElement("svg", {
  fill: "none",
  stroke: "currentColor",
  viewBox: "0 0 24 24",
  width: "16",
  height: "16"
}, React.createElement("path", {
  strokeLinecap: "round",
  strokeLinejoin: "round",
  strokeWidth: 2,
  d: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
}));

const TrashIcon = () => React.createElement("svg", {
  fill: "none",
  stroke: "currentColor",
  viewBox: "0 0 24 24",
  width: "16",
  height: "16"
}, React.createElement("path", {
  strokeLinecap: "round",
  strokeLinejoin: "round",
  strokeWidth: 2,
  d: "M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
}));

const CloseIcon = () => React.createElement("svg", {
  fill: "none",
  stroke: "currentColor",
  viewBox: "0 0 24 24",
  width: "20",
  height: "20"
}, React.createElement("path", {
  strokeLinecap: "round",
  strokeLinejoin: "round",
  strokeWidth: 2,
  d: "M6 18L18 6M6 6l12 12"
}));

const EmptyIcon = () => React.createElement("svg", {
  fill: "none",
  stroke: "currentColor",
  viewBox: "0 0 24 24"
}, React.createElement("path", {
  strokeLinecap: "round",
  strokeLinejoin: "round",
  strokeWidth: 2,
  d: "M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
}));

// Components
const StatsCard = ({ number, label, color = "var(--primary)" }) => 
  React.createElement("div", { className: "stat-card" },
    React.createElement("div", { 
      className: "stat-number", 
      style: { color } 
    }, number),
    React.createElement("div", { className: "stat-label" }, label)
  );

const LogTable = ({ logs, onRowClick }) => {
  if (logs.length === 0) {
    return React.createElement("div", { className: "empty-state" },
      React.createElement(EmptyIcon),
      React.createElement("h3", null, "Нет логов"),
      React.createElement("p", null, "Логи звонков появятся здесь")
    );
  }

  return React.createElement("div", { className: "table-container" },
    React.createElement("table", { className: "table" },
      React.createElement("thead", null,
        React.createElement("tr", null,
          ["ID", "Номер телефона", "Время начала", "Длительность", "Статус"].map((header) =>
            React.createElement("th", { key: header }, header)
          )
        )
      ),
      React.createElement("tbody", null,
        logs.map((log) =>
          React.createElement("tr", {
            key: log.id,
            onClick: () => onRowClick(log)
          },
            React.createElement("td", null, 
              React.createElement("code", null, log.id.slice(0, 8) + "...")
            ),
            React.createElement("td", null, log.callerId || "—"),
            React.createElement("td", null, formatDate(log.startTime)),
            React.createElement("td", null, formatDuration(log.startTime, log.endTime)),
            React.createElement("td", null,
              React.createElement("span", { 
                className: `status ${log.status}` 
              }, log.status)
            )
          )
        )
      )
    )
  );
};

const Modal = ({ log, onClose }) => {
  if (!log) return null;

  let transcript = [];
  try {
    transcript = JSON.parse(log.transcript_json);
  } catch (e) {
    transcript = [{ speaker: 'system', text: 'Ошибка в формате диалога' }];
  }

  return React.createElement("div", { 
    className: "modal show", 
    onClick: onClose 
  },
    React.createElement("div", { 
      className: "modal-content", 
      onClick: (e) => e.stopPropagation() 
    },
      React.createElement("div", { className: "modal-header" },
        React.createElement("h3", null, `Детали звонка`),
        React.createElement("button", { 
          className: "close-btn", 
          onClick: onClose 
        }, React.createElement(CloseIcon))
      ),
      React.createElement("div", { className: "modal-body" },
        React.createElement("div", { className: "info-grid" },
          React.createElement("div", { className: "info-item" },
            React.createElement("div", { className: "info-label" }, "ID звонка"),
            React.createElement("div", { className: "info-value" }, 
              React.createElement("code", null, log.id)
            )
          ),
          React.createElement("div", { className: "info-item" },
            React.createElement("div", { className: "info-label" }, "Номер телефона"),
            React.createElement("div", { className: "info-value" }, log.callerId || "Не указан")
          ),
          React.createElement("div", { className: "info-item" },
            React.createElement("div", { className: "info-label" }, "Время начала"),
            React.createElement("div", { className: "info-value" }, formatDate(log.startTime))
          ),
          React.createElement("div", { className: "info-item" },
            React.createElement("div", { className: "info-label" }, "Время окончания"),
            React.createElement("div", { className: "info-value" }, formatDate(log.endTime))
          ),
          React.createElement("div", { className: "info-item" },
            React.createElement("div", { className: "info-label" }, "Длительность"),
            React.createElement("div", { className: "info-value" }, formatDuration(log.startTime, log.endTime))
          ),
          React.createElement("div", { className: "info-item" },
            React.createElement("div", { className: "info-label" }, "Статус"),
            React.createElement("div", { className: "info-value" },
              React.createElement("span", { 
                className: `status ${log.status}` 
              }, log.status)
            )
          )
        ),
        React.createElement("div", { className: "transcript" },
          React.createElement("h4", null, "Транскрипт разговора"),
          transcript.map((turn, index) =>
            React.createElement("div", { 
              key: index, 
              className: `turn ${turn.speaker}` 
            }, turn.text)
          )
        )
      )
    )
  );
};

const KnowledgeBaseModal = ({ content, onClose }) => {
  if (!content) return null;

  return React.createElement("div", { 
    className: "modal show", 
    onClick: onClose 
  },
    React.createElement("div", { 
      className: "modal-content", 
      onClick: (e) => e.stopPropagation() 
    },
      React.createElement("div", { className: "modal-header" },
        React.createElement("h3", null, "База знаний"),
        React.createElement("button", { 
          className: "close-btn", 
          onClick: onClose 
        }, React.createElement(CloseIcon))
      ),
      React.createElement("div", { className: "modal-body" },
        React.createElement("pre", { 
          style: { 
            whiteSpace: 'pre-wrap', 
            lineHeight: '1.6',
            background: 'var(--bg-primary)',
            padding: '1rem',
            borderRadius: '0.5rem',
            border: '1px solid var(--border)'
          } 
        }, content.text || content.error)
      )
    )
  );
};

const App = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [modalLog, setModalLog] = useState(null);
  const [kbContent, setKbContent] = useState(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const stats = useMemo(() => {
    const total = logs.length;
    const completed = logs.filter(log => log.status === 'Completed').length;
    const failed = logs.filter(log => log.status === 'Failed').length;
    const interrupted = logs.filter(log => log.status === 'Interrupted').length;
    
    return { total, completed, failed, interrupted };
  }, [logs]);

  const fetchLogs = async (searchQuery, isInitialLoad = false) => {
    if (isInitialLoad) setLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append('q', searchQuery);
      if (dateFrom) params.append('date_from', new Date(dateFrom).toISOString());
      if (dateTo) params.append('date_to', new Date(dateTo).toISOString());
      
      const url = `/logs?${params.toString()}`;
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`Ошибка ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setLogs(data);
    } catch (err) {
      setError(err.message);
    } finally {
      if (isInitialLoad) setLoading(false);
    }
  };

  const showKnowledgeBase = async () => {
    try {
      const response = await fetch("/kb");
      const data = await response.json();
      setKbContent(data);
    } catch (err) {
      setKbContent({ error: "Ошибка загрузки базы знаний" });
    }
  };

  const clearAllLogs = async () => {
    if (window.confirm("Вы уверены, что хотите удалить ВСЕ логи? Это действие необратимо.")) {
      setError(null);
      try {
        const response = await fetch("/logs", { method: 'DELETE' });
        if (!response.ok) {
          throw new Error(`Ошибка ${response.status}: ${response.statusText}`);
        }
        fetchLogs(query, true);
      } catch (err) {
        setError(err.message);
      }
    }
  };

  const debouncedFetch = useCallback(
    debounce((searchQuery) => fetchLogs(searchQuery), 300), 
    [dateFrom, dateTo]
  );

  useEffect(() => {
    fetchLogs(query, true);
    const intervalId = setInterval(() => {
      if (document.activeElement.tagName !== 'INPUT' && document.activeElement.type !== 'date') {
        fetchLogs(query);
      }
    }, 5000);
    return () => clearInterval(intervalId);
  }, [query, dateFrom, dateTo]);

  useEffect(() => {
    debouncedFetch(query);
  }, [query, debouncedFetch]);

  return React.createElement("div", { className: "container" },
    React.createElement("div", { className: "header" },
      React.createElement("h1", null, "Admin Panel"),
      React.createElement("div", { style: { color: 'var(--text-secondary)', fontSize: '0.875rem' } },
        "Управление логами чат-бота"
      )
    ),

    React.createElement("div", { className: "stats-grid" },
        React.createElement(StatsCard, { 
            number: stats.total, 
            label: "Всего звонков",
            color: "var(--primary)"
          }),
          React.createElement(StatsCard, { 
            number: stats.completed, 
            label: "Завершенных",
            color: "var(--success)"
          }),
          React.createElement(StatsCard, { 
            number: stats.interrupted, 
            label: "Прерванных",
            color: "var(--warning)"
          }),
          React.createElement(StatsCard, { 
            number: stats.failed, 
            label: "Неудачных",
            color: "var(--danger)"
          })
    ),

    React.createElement("div", { className: "controls" },
      React.createElement("div", { className: "search-container" },
        React.createElement(SearchIcon),
        React.createElement("input", {
          type: "text",
          className: "search-input",
          placeholder: "Поиск по номеру или диалогу...",
          value: query,
          onChange: (e) => setQuery(e.target.value)
        })
      ),
      React.createElement("input", {
        type: "date",
        className: "search-input",
        value: dateFrom,
        onChange: (e) => setDateFrom(e.target.value)
      }),
      React.createElement("input", {
        type: "date",
        className: "search-input",
        value: dateTo,
        onChange: (e) => setDateTo(e.target.value)
      }),
      React.createElement("a", {
        href: "/logs/csv",
        className: "btn btn-success",
        style: { 
          pointerEvents: !logs.length ? "none" : "auto",
          opacity: !logs.length ? 0.5 : 1
        }
      },
        React.createElement(DownloadIcon),
        "Экспорт CSV"
      ),
      React.createElement("button", {
        className: "btn btn-primary",
        onClick: showKnowledgeBase
      },
        React.createElement(BookIcon),
        "База знаний"
      ),
      React.createElement("button", {
        className: "btn btn-danger",
        onClick: clearAllLogs,
        disabled: !logs.length
      },
        React.createElement(TrashIcon),
        "Очистить все"
      )
    ),

    error && React.createElement("div", { className: "error" },
      `⚠️ ${error}`
    ),

    loading ? React.createElement("div", { className: "loading" },
      React.createElement("div", { className: "spinner" })
    ) : React.createElement(LogTable, { 
      logs: logs, 
      onRowClick: setModalLog 
    }),

    React.createElement(Modal, { 
      log: modalLog, 
      onClose: () => setModalLog(null) 
    }),
    
    React.createElement(KnowledgeBaseModal, { 
      content: kbContent, 
      onClose: () => setKbContent(null) 
    })
  );
};

createRoot(document.getElementById("root")).render(React.createElement(App));
