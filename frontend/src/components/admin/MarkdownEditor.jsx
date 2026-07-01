import React, { useRef } from 'react';
import { Bold, Italic, List, Link } from 'lucide-react';

export default function MarkdownEditor({ value, onChange, placeholder, style, autoFocus }) {
  const textareaRef = useRef(null);

  const insertFormatting = (prefix, suffix) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value;
    const selectedText = text.substring(start, end);

    const newText = text.substring(0, start) + prefix + selectedText + suffix + text.substring(end);
    
    // Create synthetic event to trigger onChange
    const event = {
      target: {
        value: newText
      }
    };
    onChange(event);

    // Restore cursor position asynchronously after render
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + prefix.length, end + prefix.length + selectedText.length);
    }, 0);
  };

  const handleKeyDown = (e) => {
    // Only capture ctrl/cmd when inside textarea
    if (e.ctrlKey || e.metaKey) {
      switch (e.key.toLowerCase()) {
        case 'b':
          e.preventDefault();
          insertFormatting('**', '**');
          break;
        case 'i':
          e.preventDefault();
          insertFormatting('*', '*');
          break;
        default:
          break;
      }
    }
  };

  return (
    <div style={{ border: '1px solid #cbd5e1', borderRadius: '6px', overflow: 'hidden', backgroundColor: 'white' }}>
      <div style={{ display: 'flex', gap: '4px', padding: '6px 8px', backgroundColor: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
        <button 
          type="button" 
          onClick={(e) => { e.stopPropagation(); insertFormatting('**', '**'); }}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', borderRadius: '4px', color: '#475569', display: 'flex', alignItems: 'center' }}
          title="In đậm (Ctrl+B)"
        >
          <Bold size={16} />
        </button>
        <button 
          type="button" 
          onClick={(e) => { e.stopPropagation(); insertFormatting('*', '*'); }}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', borderRadius: '4px', color: '#475569', display: 'flex', alignItems: 'center' }}
          title="In nghiêng (Ctrl+I)"
        >
          <Italic size={16} />
        </button>
        <div style={{ width: '1px', backgroundColor: '#cbd5e1', margin: '0 4px' }}></div>
        <button 
          type="button" 
          onClick={(e) => { e.stopPropagation(); insertFormatting('- ', ''); }}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', borderRadius: '4px', color: '#475569', display: 'flex', alignItems: 'center' }}
          title="Danh sách"
        >
          <List size={16} />
        </button>
        <button 
          type="button" 
          onClick={(e) => { e.stopPropagation(); insertFormatting('[', '](url)'); }}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', borderRadius: '4px', color: '#475569', display: 'flex', alignItems: 'center' }}
          title="Chèn Link"
        >
          <Link size={16} />
        </button>
      </div>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={onChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        style={{
          width: '100%',
          border: 'none',
          padding: '10px',
          outline: 'none',
          resize: 'vertical',
          minHeight: '120px',
          boxSizing: 'border-box',
          fontFamily: 'inherit',
          ...style
        }}
        autoFocus={autoFocus}
      />
    </div>
  );
}
