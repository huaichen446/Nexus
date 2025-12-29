import {
  Menu,
  PencilLine,
  FolderPlus,
  MessageSquareText,
  Settings,
} from "lucide-react";
import { CollapsibleSection } from "../ui/CollapsibleSection";
import type { Chat } from "../../types/chat";
import type { Project } from "../../types/project";

interface SidebarProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  chats: Chat[];
  projects: Project[];
  activeChatId?: string;
  activeProjectId?: string;
}

export function Sidebar({
  isSidebarOpen,
  onToggleSidebar,
  chats,
  projects,
  activeChatId,
  activeProjectId,
}: SidebarProps) {
  return (
    <div
      className={`
        relative flex h-full flex-col bg-[#F0F4F9]
        transition-[width] duration-300 ease-in-out
        ${isSidebarOpen ? "w-[280px]" : "w-0"}
      `}
    >
      <div
        className={`
          flex h-full flex-col px-3 py-3
          ${isSidebarOpen ? "opacity-100" : "pointer-events-none opacity-0"}
          transition-opacity duration-200
        `}
      >
        <div>
          <div className="mb-3 flex items-center justify-between">
            <button
              type="button"
              onClick={onToggleSidebar}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/80 text-slate-700 shadow-sm hover:bg-white"
            >
              <Menu className="h-5 w-5" />
            </button>
          </div>

          <button
            type="button"
            className="mb-2 flex w-full items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-md hover:bg-slate-800"
          >
            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-white/15">
              <PencilLine className="h-4 w-4" />
            </span>
            <span>New chat</span>
          </button>

          <button
            type="button"
            className="mb-4 flex w-full items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-sm font-medium text-slate-800 shadow-sm hover:bg-white"
          >
            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-900/5">
              <FolderPlus className="h-4 w-4" />
            </span>
            <span>New project</span>
          </button>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto pb-3">
          <CollapsibleSection title="Chats" defaultOpen>
            {chats.map((chat) => {
              const isActive = chat.id === activeChatId;
              return (
                <button
                  key={chat.id}
                  type="button"
                  className={`
                    flex w-full items-center gap-2 rounded-2xl px-3 py-2 text-left text-sm
                    transition-colors
                    ${
                      isActive
                        ? "bg-slate-900 text-white"
                        : "bg-transparent text-slate-800 hover:bg-slate-200/70"
                    }
                  `}
                >
                  <span
                    className={`
                      inline-flex h-6 w-6 items-center justify-center rounded-full
                      ${
                        isActive
                          ? "bg-white/15 text-white"
                          : "bg-slate-900/5 text-slate-600"
                      }
                    `}
                  >
                    <MessageSquareText className="h-3.5 w-3.5" />
                  </span>
                  <span className="truncate">{chat.title}</span>
                </button>
              );
            })}
          </CollapsibleSection>

          <CollapsibleSection title="Projects" defaultOpen>
            {projects.map((project) => {
              const isActive = project.id === activeProjectId;
              return (
                <button
                  key={project.id}
                  type="button"
                  className={`
                    flex w-full items-center gap-2 rounded-2xl px-3 py-2 text-left text-sm
                    transition-colors
                    ${
                      isActive
                        ? "bg-slate-900 text-white"
                        : "bg-transparent text-slate-800 hover:bg-slate-200/70"
                    }
                  `}
                >
                  <span
                    className={`
                      inline-flex h-6 w-6 items-center justify-center rounded-full
                      ${
                        isActive
                          ? "bg-white/15 text-white"
                          : "bg-slate-900/5 text-slate-600"
                      }
                    `}
                  >
                    <FolderPlus className="h-3.5 w-3.5" />
                  </span>
                  <span className="truncate">{project.name}</span>
                </button>
              );
            })}
          </CollapsibleSection>
        </div>

        <div className="mt-2 border-t border-slate-200 pt-3">
          <button
            type="button"
            className="flex w-full items-center justify-between rounded-full px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100/80"
          >
            <span>Settings and help</span>
            <Settings className="h-4 w-4" />
          </button>
        </div>
      </div>

      {!isSidebarOpen && (
        <button
          type="button"
          onClick={onToggleSidebar}
          className="absolute left-2 top-3 inline-flex h-9 w-9 items-center justify-center rounded-full bg-[#F0F4F9] text-slate-700 shadow-md"
        >
          <Menu className="h-5 w-5" />
        </button>
      )}
    </div>
  );
}












