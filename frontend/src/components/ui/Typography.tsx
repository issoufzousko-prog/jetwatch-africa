import React from "react";

export function TypographyH1({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <h1 className={`scroll-m-20 text-4xl font-extrabold tracking-tight text-balance ${className}`}>
      {children}
    </h1>
  );
}

export function TypographyH2({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <h2 className={`scroll-m-20 border-b pb-2 text-3xl font-semibold tracking-tight first:mt-0 ${className}`}>
      {children}
    </h2>
  );
}

export function TypographyH3({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <h3 className={`scroll-m-20 text-2xl font-semibold tracking-tight ${className}`}>
      {children}
    </h3>
  );
}

export function TypographyP({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={`leading-7 [&:not(:first-child)]:mt-6 ${className}`}>
      {children}
    </p>
  );
}

export function TypographyBlockquote({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <blockquote className={`mt-6 border-l-2 pl-6 italic ${className}`}>
      {children}
    </blockquote>
  );
}

export function TypographyList({ items, className = "" }: { items: React.ReactNode[]; className?: string }) {
  return (
    <ul className={`my-6 ml-6 list-disc [&>li]:mt-2 ${className}`}>
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  );
}

interface TableColumn {
  header: React.ReactNode;
  accessor: string;
}

export function TypographyTable({ 
  columns, 
  data, 
  className = "" 
}: { 
  columns: TableColumn[]; 
  data: any[]; 
  className?: string; 
}) {
  return (
    <div className={`my-6 w-full overflow-y-auto ${className}`}>
      <table className="w-full">
        <thead>
          <tr className="m-0 border-t p-0 even:bg-muted">
            {columns.map((col, i) => (
              <th key={i} className="border px-4 py-2 text-left font-bold [&[align=center]]:text-center [&[align=right]]:text-right">
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="m-0 border-t p-0 even:bg-muted">
              {columns.map((col, j) => (
                <td key={j} className="border px-4 py-2 text-left [&[align=center]]:text-center [&[align=right]]:text-right">
                  {row[col.accessor]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
